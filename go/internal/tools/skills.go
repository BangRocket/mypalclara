package tools

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/BangRocket/mypalclara/go/internal/llm"
)

// DefaultSkillsDir is the default directory for skill files.
const DefaultSkillsDir = "./workspace/skills"

// SkillTools provides skill loading and listing.
type SkillTools struct {
	skillsDir string
}

// NewSkillTools creates skill tools with the given directory.
// If skillsDir is empty, DefaultSkillsDir is used.
func NewSkillTools(skillsDir string) *SkillTools {
	if skillsDir == "" {
		skillsDir = DefaultSkillsDir
	}
	return &SkillTools{skillsDir: skillsDir}
}

// Register adds skill tools to the registry.
func (st *SkillTools) Register(reg *Registry) {
	reg.Register(ToolDef{
		Schema: llm.ToolSchema{
			Name:        "load_skill",
			Description: "Load skill instructions from the workspace skills directory.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"skill_name": map[string]any{
						"type":        "string",
						"description": "Name of the skill to load (directory name under workspace/skills/).",
					},
				},
				"required": []string{"skill_name"},
			},
		},
		Handler: st.handleLoad,
	})

	reg.Register(ToolDef{
		Schema: llm.ToolSchema{
			Name:        "list_skills",
			Description: "List available skills in the workspace skills directory.",
			Parameters: map[string]any{
				"type":       "object",
				"properties": map[string]any{},
			},
		},
		Handler: st.handleList,
	})
}

func (st *SkillTools) handleLoad(_ context.Context, args map[string]any, _ string) (string, error) {
	name, _ := args["skill_name"].(string)
	if name == "" {
		return "", fmt.Errorf("skill_name is required")
	}

	safe := sanitizeFilename(name)
	if safe == "" {
		return "", fmt.Errorf("invalid skill name: %q", name)
	}

	skillDir := filepath.Join(st.skillsDir, safe)
	info, err := os.Stat(skillDir)
	if err != nil || !info.IsDir() {
		return "", fmt.Errorf("skill %q not found", safe)
	}

	// Look for instruction files in order of preference.
	candidates := []string{"instructions.md", "README.md", "prompt.md", "instructions.txt"}
	for _, candidate := range candidates {
		path := filepath.Join(skillDir, candidate)
		data, err := os.ReadFile(path)
		if err == nil {
			return string(data), nil
		}
	}

	return "", fmt.Errorf("no instruction file found in skill %q (looked for %s)", safe, strings.Join(candidates, ", "))
}

func (st *SkillTools) handleList(_ context.Context, _ map[string]any, _ string) (string, error) {
	entries, err := os.ReadDir(st.skillsDir)
	if err != nil {
		if os.IsNotExist(err) {
			return "No skills directory found.", nil
		}
		return "", fmt.Errorf("failed to list skills: %w", err)
	}

	var skills []string
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		// Check if it has an instruction file.
		candidates := []string{"instructions.md", "README.md", "prompt.md", "instructions.txt"}
		for _, c := range candidates {
			if _, err := os.Stat(filepath.Join(st.skillsDir, e.Name(), c)); err == nil {
				skills = append(skills, e.Name())
				break
			}
		}
	}

	if len(skills) == 0 {
		return "No skills found.", nil
	}

	var sb strings.Builder
	sb.WriteString("Available skills:\n")
	for _, s := range skills {
		sb.WriteString(fmt.Sprintf("- %s\n", s))
	}
	return sb.String(), nil
}
