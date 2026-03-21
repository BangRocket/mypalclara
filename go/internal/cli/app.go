package cli

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/glamour"
	"github.com/charmbracelet/lipgloss"

	gateway "github.com/BangRocket/mypalclara/go/internal/gateway"
)

// ChatEntry represents a single entry in the chat log.
type ChatEntry struct {
	Role     string // "user", "assistant", "system", "tool"
	Content  string
	ToolInfo *ToolInfo
}

// ToolInfo holds metadata about a tool execution displayed in the chat log.
type ToolInfo struct {
	Name      string
	Status    string // "running", "success", "error"
	Args      string
	Output    string
	Collapsed bool
}

// Model is the top-level bubbletea model for the Clara CLI TUI.
type Model struct {
	chatLog    []ChatEntry
	input      string
	status     string
	connected  bool
	thinking   bool
	elapsed    time.Duration
	gateway    *GatewayClient
	gatewayURL string
	width      int
	height     int
	viewport   int // scroll offset (lines from bottom)
	theme      *Theme
	history    []string // input history
	historyIdx int
	tier       string
	userID     string

	spinner    spinner.Model
	thinkStart time.Time
	activeReq  string // current in-flight request ID
	commands   []SlashCommand
	msgCh      <-chan *gateway.GatewayMessage
	ctx        context.Context
	cancel     context.CancelFunc

	// accumulated streaming response for the current request
	streaming      bool
	streamAccum    string

	// ctrlCPressed tracks whether Ctrl+C was pressed once (to clear input)
	// vs twice (to quit).
	ctrlCPressed bool
}

// NewModel creates a new TUI model that will connect to the given gateway URL.
func NewModel(gatewayURL, userID string) Model {
	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = lipgloss.NewStyle().Foreground(lipgloss.Color("205"))

	ctx, cancel := context.WithCancel(context.Background())

	m := Model{
		gatewayURL: gatewayURL,
		gateway:    NewGatewayClient(gatewayURL),
		theme:      NewTheme(),
		spinner:    s,
		tier:       "mid",
		userID:     userID,
		historyIdx: -1,
		ctx:        ctx,
		cancel:     cancel,
	}
	m.commands = DefaultCommands(&m)
	return m
}

// --- bubbletea interface ---

// Init returns the initial commands: connect to gateway and start spinner.
func (m Model) Init() tea.Cmd {
	return tea.Batch(
		m.connectCmd(),
		m.spinner.Tick,
	)
}

// Update handles messages from bubbletea.
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmds []tea.Cmd

	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height

	case tea.KeyMsg:
		cmd := m.handleKey(msg)
		if cmd != nil {
			cmds = append(cmds, cmd)
		}

	case spinner.TickMsg:
		if m.thinking {
			m.elapsed = time.Since(m.thinkStart)
			var cmd tea.Cmd
			m.spinner, cmd = m.spinner.Update(msg)
			cmds = append(cmds, cmd)
		}

	case connectedMsg:
		m.connected = msg.ok
		if msg.ok {
			m.status = "connected"
			m.msgCh = m.gateway.ReadMessages(m.ctx)
			cmds = append(cmds, m.waitForGatewayMsg())
		} else {
			m.status = "connection failed: " + msg.err
			m.chatLog = append(m.chatLog, ChatEntry{
				Role:    "system",
				Content: "Failed to connect to gateway: " + msg.err,
			})
		}

	case gatewayMsg:
		cmd := m.handleGatewayMessage(msg.msg)
		if cmd != nil {
			cmds = append(cmds, cmd)
		}
		// Continue reading.
		if m.msgCh != nil {
			cmds = append(cmds, m.waitForGatewayMsg())
		}

	case disconnectedMsg:
		m.connected = false
		m.status = "disconnected"
		m.msgCh = nil
		m.chatLog = append(m.chatLog, ChatEntry{
			Role:    "system",
			Content: "Disconnected from gateway.",
		})

	case systemMsg:
		m.chatLog = append(m.chatLog, ChatEntry{
			Role:    "system",
			Content: msg.text,
		})
		m.viewport = 0

	case clearChatMsg:
		m.chatLog = nil
		m.viewport = 0

	case cancelRequestMsg:
		if m.activeReq != "" {
			_ = m.gateway.CancelRequest(m.activeReq)
			m.thinking = false
			m.streaming = false
			m.activeReq = ""
			m.status = "cancelled"
		}
	}

	return m, tea.Batch(cmds...)
}

// View renders the TUI.
func (m Model) View() string {
	if m.width == 0 {
		return "Initializing..."
	}

	var sections []string

	// Header
	header := m.renderHeader()
	sections = append(sections, header)

	// Status line
	statusLine := m.renderStatus()

	// Editor
	editor := m.renderEditor()

	// Calculate chat area height.
	headerH := lipgloss.Height(header)
	statusH := lipgloss.Height(statusLine)
	editorH := lipgloss.Height(editor)
	chatH := m.height - headerH - statusH - editorH
	if chatH < 1 {
		chatH = 1
	}

	// Chat log
	chat := m.renderChat(chatH)
	sections = append(sections, chat)

	// Status + Editor
	sections = append(sections, statusLine)
	sections = append(sections, editor)

	return lipgloss.JoinVertical(lipgloss.Left, sections...)
}

// --- key handling ---

func (m *Model) handleKey(msg tea.KeyMsg) tea.Cmd {
	switch msg.Type {
	case tea.KeyCtrlC:
		if m.input != "" {
			m.input = ""
			m.ctrlCPressed = false
			return nil
		}
		if m.ctrlCPressed {
			return tea.Quit
		}
		m.ctrlCPressed = true
		m.chatLog = append(m.chatLog, ChatEntry{
			Role:    "system",
			Content: "Press Ctrl+C again to exit.",
		})
		return nil

	case tea.KeyEsc:
		if m.activeReq != "" {
			_ = m.gateway.CancelRequest(m.activeReq)
			m.thinking = false
			m.streaming = false
			m.activeReq = ""
			m.status = "cancelled"
		}
		return nil

	case tea.KeyEnter:
		// Alt+Enter inserts newline.
		if msg.Alt {
			m.input += "\n"
			return nil
		}
		return m.submitInput()

	case tea.KeyUp:
		if len(m.history) > 0 {
			if m.historyIdx < 0 {
				m.historyIdx = len(m.history) - 1
			} else if m.historyIdx > 0 {
				m.historyIdx--
			}
			m.input = m.history[m.historyIdx]
		}
		return nil

	case tea.KeyDown:
		if m.historyIdx >= 0 {
			m.historyIdx++
			if m.historyIdx >= len(m.history) {
				m.historyIdx = -1
				m.input = ""
			} else {
				m.input = m.history[m.historyIdx]
			}
		}
		return nil

	case tea.KeyPgUp:
		m.viewport += 5
		return nil

	case tea.KeyPgDown:
		m.viewport -= 5
		if m.viewport < 0 {
			m.viewport = 0
		}
		return nil

	case tea.KeyBackspace:
		if len(m.input) > 0 {
			m.input = m.input[:len(m.input)-1]
		}
		return nil

	case tea.KeyRunes:
		m.ctrlCPressed = false
		m.input += string(msg.Runes)
		return nil

	case tea.KeySpace:
		m.input += " "
		return nil

	case tea.KeyTab:
		m.input += "  "
		return nil

	default:
		return nil
	}
}

func (m *Model) submitInput() tea.Cmd {
	text := strings.TrimSpace(m.input)
	if text == "" {
		return nil
	}

	// Save to history.
	m.history = append(m.history, text)
	m.historyIdx = -1
	m.input = ""

	// Check for slash commands.
	cmd, args := ParseSlashCommand(text, m.commands)
	if cmd != nil {
		return cmd.Handler(args)
	}

	// Send as chat message.
	m.chatLog = append(m.chatLog, ChatEntry{Role: "user", Content: text})
	m.viewport = 0

	if !m.connected {
		return func() tea.Msg {
			return systemMsg{text: "Not connected to gateway."}
		}
	}

	content := text
	if m.tier != "mid" {
		content = "!" + m.tier + " " + content
	}

	reqID, err := m.gateway.SendMessage(content, m.userID)
	if err != nil {
		return func() tea.Msg {
			return systemMsg{text: "Send failed: " + err.Error()}
		}
	}

	m.activeReq = reqID
	m.thinking = true
	m.thinkStart = time.Now()
	m.streaming = false
	m.streamAccum = ""
	m.status = "thinking..."

	return m.spinner.Tick
}

// --- gateway message handling ---

func (m *Model) handleGatewayMessage(msg *gateway.GatewayMessage) tea.Cmd {
	switch msg.Type {
	case gateway.MsgTypeResponseStart:
		m.thinking = true
		m.status = "responding..."
		if rs, ok := msg.Payload.(gateway.ResponseStart); ok && rs.ModelTier != "" {
			m.status = fmt.Sprintf("responding (%s)...", rs.ModelTier)
		}

	case gateway.MsgTypeResponseChunk:
		if chunk, ok := msg.Payload.(gateway.ResponseChunk); ok {
			if !m.streaming {
				m.streaming = true
				m.streamAccum = ""
			}
			m.streamAccum += chunk.Chunk
			m.viewport = 0
			// Update the last assistant entry or create one.
			m.updateStreamEntry()
		}

	case gateway.MsgTypeResponseEnd:
		if end, ok := msg.Payload.(gateway.ResponseEnd); ok {
			m.thinking = false
			m.streaming = false
			m.activeReq = ""
			m.status = "connected"

			// Replace streaming entry with final text.
			finalText := end.FullText
			if finalText == "" {
				finalText = m.streamAccum
			}
			m.updateFinalEntry(finalText)
			m.viewport = 0
		}

	case gateway.MsgTypeToolStart:
		if ts, ok := msg.Payload.(gateway.ToolStart); ok {
			argsStr := ""
			if ts.Arguments != nil {
				for k, v := range ts.Arguments {
					argsStr += fmt.Sprintf("%s=%v ", k, v)
				}
			}
			m.chatLog = append(m.chatLog, ChatEntry{
				Role: "tool",
				ToolInfo: &ToolInfo{
					Name:   ts.ToolName,
					Status: "running",
					Args:   strings.TrimSpace(argsStr),
				},
			})
			desc := ts.ToolName
			if ts.Description != "" {
				desc = ts.Description
			}
			m.status = fmt.Sprintf("running tool: %s", desc)
			m.viewport = 0
		}

	case gateway.MsgTypeToolResult:
		if tr, ok := msg.Payload.(gateway.ToolResult); ok {
			// Update the last tool entry with this name.
			for i := len(m.chatLog) - 1; i >= 0; i-- {
				if m.chatLog[i].ToolInfo != nil && m.chatLog[i].ToolInfo.Name == tr.ToolName && m.chatLog[i].ToolInfo.Status == "running" {
					status := "success"
					if !tr.Success {
						status = "error"
					}
					m.chatLog[i].ToolInfo.Status = status
					m.chatLog[i].ToolInfo.Output = tr.OutputPreview
					m.chatLog[i].ToolInfo.Collapsed = true
					break
				}
			}
			m.status = "thinking..."
		}

	case gateway.MsgTypeError:
		if errMsg, ok := msg.Payload.(gateway.ErrorMessage); ok {
			m.thinking = false
			m.streaming = false
			m.activeReq = ""
			m.status = "error"
			m.chatLog = append(m.chatLog, ChatEntry{
				Role:    "system",
				Content: "Error: " + errMsg.Message,
			})
			m.viewport = 0
		}

	case gateway.MsgTypeCancelled:
		m.thinking = false
		m.streaming = false
		m.activeReq = ""
		m.status = "connected"
	}
	return nil
}

func (m *Model) updateStreamEntry() {
	// Find the last assistant entry or create one.
	if len(m.chatLog) > 0 && m.chatLog[len(m.chatLog)-1].Role == "assistant" {
		m.chatLog[len(m.chatLog)-1].Content = m.streamAccum
	} else {
		m.chatLog = append(m.chatLog, ChatEntry{
			Role:    "assistant",
			Content: m.streamAccum,
		})
	}
}

func (m *Model) updateFinalEntry(text string) {
	if len(m.chatLog) > 0 && m.chatLog[len(m.chatLog)-1].Role == "assistant" {
		m.chatLog[len(m.chatLog)-1].Content = text
	} else {
		m.chatLog = append(m.chatLog, ChatEntry{
			Role:    "assistant",
			Content: text,
		})
	}
}

// --- rendering ---

func (m Model) renderHeader() string {
	connStatus := "disconnected"
	connColor := lipgloss.Color("204")
	if m.connected {
		connStatus = "connected"
		connColor = lipgloss.Color("78")
	}

	statusStyle := lipgloss.NewStyle().Foreground(connColor)

	header := fmt.Sprintf("clara-cli  %s  %s",
		m.theme.Dim.Render(m.gatewayURL),
		statusStyle.Render(connStatus),
	)
	return m.theme.Header.Width(m.width - 2).Render(header)
}

func (m Model) renderStatus() string {
	var parts []string

	if m.thinking {
		elapsed := m.elapsed.Truncate(100 * time.Millisecond)
		parts = append(parts, fmt.Sprintf("%s %s  %s",
			m.spinner.View(),
			m.status,
			m.theme.Dim.Render(elapsed.String()),
		))
	} else {
		parts = append(parts, m.status)
	}

	if m.tier != "mid" {
		parts = append(parts, m.theme.Dim.Render(fmt.Sprintf("[%s]", m.tier)))
	}

	line := strings.Join(parts, "  ")
	return m.theme.Status.Width(m.width).Render(line)
}

func (m Model) renderEditor() string {
	prompt := "> "
	display := m.input
	if display == "" {
		display = m.theme.Dim.Render("Type a message...")
	}

	content := prompt + display + "\u2588" // block cursor

	return m.theme.Editor.Width(m.width - 4).Render(content)
}

func (m Model) renderChat(height int) string {
	if len(m.chatLog) == 0 {
		empty := m.theme.Dim.Render("No messages yet. Type /help for commands.")
		return lipgloss.NewStyle().Height(height).Render(empty)
	}

	contentWidth := m.width - 4
	if contentWidth < 20 {
		contentWidth = 20
	}

	var lines []string
	for _, entry := range m.chatLog {
		rendered := m.renderEntry(entry, contentWidth)
		lines = append(lines, rendered)
	}

	all := strings.Join(lines, "\n")
	allLines := strings.Split(all, "\n")

	// Apply scroll offset.
	totalLines := len(allLines)
	if m.viewport > totalLines-height {
		m.viewport = totalLines - height
	}

	endIdx := totalLines - m.viewport
	startIdx := endIdx - height
	if startIdx < 0 {
		startIdx = 0
	}
	if endIdx < 0 {
		endIdx = 0
	}
	if endIdx > totalLines {
		endIdx = totalLines
	}

	visible := allLines[startIdx:endIdx]

	// Pad to fill height.
	for len(visible) < height {
		visible = append([]string{""}, visible...)
	}

	return strings.Join(visible, "\n")
}

func (m Model) renderEntry(entry ChatEntry, width int) string {
	switch entry.Role {
	case "user":
		return m.theme.UserMsg.Width(width).Render("You: " + entry.Content)

	case "assistant":
		rendered := m.renderMarkdown(entry.Content, width)
		return rendered

	case "system":
		return m.theme.System.Render(entry.Content)

	case "tool":
		return m.renderTool(entry, width)

	default:
		return entry.Content
	}
}

func (m Model) renderMarkdown(text string, width int) string {
	style := "dark"
	if !m.theme.Dark {
		style = "light"
	}

	r, err := glamour.NewTermRenderer(
		glamour.WithStandardStyle(style),
		glamour.WithWordWrap(width),
	)
	if err != nil {
		return m.theme.Assistant.Render(text)
	}

	rendered, err := r.Render(text)
	if err != nil {
		return m.theme.Assistant.Render(text)
	}

	return strings.TrimRight(rendered, "\n")
}

func (m Model) renderTool(entry ChatEntry, width int) string {
	if entry.ToolInfo == nil {
		return ""
	}

	ti := entry.ToolInfo
	var icon string
	var nameStyle lipgloss.Style

	switch ti.Status {
	case "running":
		icon = m.spinner.View()
		nameStyle = m.theme.ToolBox.Copy()
	case "success":
		icon = m.theme.ToolOk.Render("[ok]")
		nameStyle = m.theme.ToolOk
	case "error":
		icon = m.theme.ToolErr.Render("[err]")
		nameStyle = m.theme.ToolErr
	}

	header := fmt.Sprintf("%s %s", icon, nameStyle.Render(ti.Name))

	if ti.Collapsed && ti.Output == "" {
		return header
	}

	var body strings.Builder
	body.WriteString(header)
	if ti.Args != "" {
		body.WriteString("\n  " + m.theme.Dim.Render(ti.Args))
	}
	if ti.Output != "" && !ti.Collapsed {
		body.WriteString("\n  " + m.theme.Dim.Render(ti.Output))
	}

	return m.theme.ToolBox.Width(width).Render(body.String())
}

// --- async commands ---

type connectedMsg struct {
	ok  bool
	err string
}

type gatewayMsg struct {
	msg *gateway.GatewayMessage
}

type disconnectedMsg struct{}

func (m Model) connectCmd() tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(m.ctx, 10*time.Second)
		defer cancel()

		if err := m.gateway.Connect(ctx); err != nil {
			return connectedMsg{ok: false, err: err.Error()}
		}
		return connectedMsg{ok: true}
	}
}

func (m Model) waitForGatewayMsg() tea.Cmd {
	ch := m.msgCh
	return func() tea.Msg {
		if ch == nil {
			return disconnectedMsg{}
		}
		msg, ok := <-ch
		if !ok {
			return disconnectedMsg{}
		}
		return gatewayMsg{msg: msg}
	}
}
