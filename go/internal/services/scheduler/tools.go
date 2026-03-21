package scheduler

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/BangRocket/mypalclara/go/internal/llm"
)

// ToolSchemas returns LLM tool schemas for scheduler operations.
func ToolSchemas() []llm.ToolSchema {
	return []llm.ToolSchema{
		{
			Name:        "schedule_task",
			Description: "Schedule a one-shot task to run at a specific time.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"prompt": map[string]any{
						"type":        "string",
						"description": "The prompt/instruction to execute when the task fires.",
					},
					"run_at": map[string]any{
						"type":        "string",
						"description": "When to run the task (RFC 3339 format, e.g. 2025-01-15T14:30:00Z).",
					},
					"description": map[string]any{
						"type":        "string",
						"description": "Human-readable description of the task.",
					},
				},
				"required": []string{"prompt", "run_at"},
			},
		},
		{
			Name:        "schedule_cron",
			Description: "Schedule a recurring task using a cron expression.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"prompt": map[string]any{
						"type":        "string",
						"description": "The prompt/instruction to execute on each run.",
					},
					"cron_expr": map[string]any{
						"type":        "string",
						"description": "Cron expression (e.g. '0 9 * * *' for daily at 9am).",
					},
					"description": map[string]any{
						"type":        "string",
						"description": "Human-readable description of the recurring task.",
					},
				},
				"required": []string{"prompt", "cron_expr"},
			},
		},
		{
			Name:        "list_scheduled_tasks",
			Description: "List all scheduled tasks for the current user.",
			Parameters: map[string]any{
				"type":       "object",
				"properties": map[string]any{},
			},
		},
		{
			Name:        "cancel_scheduled_task",
			Description: "Cancel a scheduled task by ID.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"task_id": map[string]any{
						"type":        "string",
						"description": "The ID of the task to cancel.",
					},
				},
				"required": []string{"task_id"},
			},
		},
	}
}

// HandleToolCall dispatches a scheduler tool call to the appropriate handler.
// Returns the result string and any error.
func HandleToolCall(s *Scheduler, ctx context.Context, toolName string, args map[string]any, userID string) (string, error) {
	switch toolName {
	case "schedule_task":
		return handleScheduleTask(s, args, userID)
	case "schedule_cron":
		return handleScheduleCron(s, args, userID)
	case "list_scheduled_tasks":
		return handleListTasks(s, userID)
	case "cancel_scheduled_task":
		return handleCancelTask(s, args)
	default:
		return "", fmt.Errorf("unknown scheduler tool: %s", toolName)
	}
}

func handleScheduleTask(s *Scheduler, args map[string]any, userID string) (string, error) {
	prompt, _ := args["prompt"].(string)
	runAtStr, _ := args["run_at"].(string)
	desc, _ := args["description"].(string)

	if prompt == "" {
		return "", fmt.Errorf("prompt is required")
	}
	if runAtStr == "" {
		return "", fmt.Errorf("run_at is required")
	}

	runAt, err := time.Parse(time.RFC3339, runAtStr)
	if err != nil {
		return "", fmt.Errorf("invalid run_at format (expected RFC 3339): %w", err)
	}

	task := &ScheduledTask{
		Type:        TaskTypeOneShot,
		Prompt:      prompt,
		UserID:      userID,
		RunAt:       &runAt,
		Description: desc,
	}
	s.AddTask(task)

	return fmt.Sprintf("Scheduled task %s to run at %s", task.ID, runAt.Format(time.RFC3339)), nil
}

func handleScheduleCron(s *Scheduler, args map[string]any, userID string) (string, error) {
	prompt, _ := args["prompt"].(string)
	cronExpr, _ := args["cron_expr"].(string)
	desc, _ := args["description"].(string)

	if prompt == "" {
		return "", fmt.Errorf("prompt is required")
	}
	if cronExpr == "" {
		return "", fmt.Errorf("cron_expr is required")
	}

	task := &ScheduledTask{
		Type:        TaskTypeCron,
		Prompt:      prompt,
		UserID:      userID,
		CronExpr:    cronExpr,
		Description: desc,
	}
	s.AddTask(task)

	return fmt.Sprintf("Scheduled cron task %s with expression %q", task.ID, cronExpr), nil
}

func handleListTasks(s *Scheduler, userID string) (string, error) {
	tasks := s.ListTasks(userID)
	if len(tasks) == 0 {
		return "No scheduled tasks.", nil
	}

	var sb strings.Builder
	for _, t := range tasks {
		sb.WriteString(fmt.Sprintf("- [%s] %s (%s) status=%s", t.ID, t.Description, t.Type, t.Status))
		if t.RunAt != nil {
			sb.WriteString(fmt.Sprintf(" run_at=%s", t.RunAt.Format(time.RFC3339)))
		}
		if t.CronExpr != "" {
			sb.WriteString(fmt.Sprintf(" cron=%q", t.CronExpr))
		}
		sb.WriteString("\n")
	}

	return sb.String(), nil
}

func handleCancelTask(s *Scheduler, args map[string]any) (string, error) {
	taskID, _ := args["task_id"].(string)
	if taskID == "" {
		return "", fmt.Errorf("task_id is required")
	}

	if s.RemoveTask(taskID) {
		return fmt.Sprintf("Cancelled task %s", taskID), nil
	}
	return "", fmt.Errorf("task %s not found", taskID)
}
