package scheduler

import (
	"context"
	"sync"
	"testing"
	"time"
)

func TestAddAndListTasks(t *testing.T) {
	s := New(nil)

	runAt := time.Now().Add(time.Hour)
	s.AddTask(&ScheduledTask{
		Type:        TaskTypeOneShot,
		Prompt:      "remind me",
		UserID:      "user-1",
		RunAt:       &runAt,
		Description: "test reminder",
	})
	s.AddTask(&ScheduledTask{
		Type:     TaskTypeCron,
		Prompt:   "daily check",
		UserID:   "user-1",
		CronExpr: "0 9 * * *",
	})
	s.AddTask(&ScheduledTask{
		Type:   TaskTypeOneShot,
		Prompt: "other user task",
		UserID: "user-2",
		RunAt:  &runAt,
	})

	// List for user-1 should return 2.
	tasks := s.ListTasks("user-1")
	if len(tasks) != 2 {
		t.Fatalf("expected 2 tasks for user-1, got %d", len(tasks))
	}

	// List for user-2 should return 1.
	tasks = s.ListTasks("user-2")
	if len(tasks) != 1 {
		t.Fatalf("expected 1 task for user-2, got %d", len(tasks))
	}

	// List all (empty userID) should return 3.
	tasks = s.ListTasks("")
	if len(tasks) != 3 {
		t.Fatalf("expected 3 total tasks, got %d", len(tasks))
	}

	// Verify auto-generated fields.
	for _, task := range tasks {
		if task.ID == "" {
			t.Error("expected task to have auto-generated ID")
		}
		if task.Status != "pending" {
			t.Errorf("expected status 'pending', got %q", task.Status)
		}
		if task.CreatedAt.IsZero() {
			t.Error("expected CreatedAt to be set")
		}
	}
}

func TestRemoveTask(t *testing.T) {
	s := New(nil)

	runAt := time.Now().Add(time.Hour)
	s.AddTask(&ScheduledTask{
		ID:     "task-1",
		Type:   TaskTypeOneShot,
		Prompt: "test",
		UserID: "user-1",
		RunAt:  &runAt,
	})

	if !s.RemoveTask("task-1") {
		t.Fatal("expected RemoveTask to return true for existing task")
	}
	if s.RemoveTask("task-1") {
		t.Fatal("expected RemoveTask to return false for already-removed task")
	}
	if s.RemoveTask("nonexistent") {
		t.Fatal("expected RemoveTask to return false for nonexistent task")
	}

	tasks := s.ListTasks("")
	if len(tasks) != 0 {
		t.Fatalf("expected 0 tasks after removal, got %d", len(tasks))
	}
}

func TestOneShotFires(t *testing.T) {
	var mu sync.Mutex
	var dispatched []*ScheduledTask

	dispatch := func(_ context.Context, task *ScheduledTask) error {
		mu.Lock()
		dispatched = append(dispatched, task)
		mu.Unlock()
		return nil
	}

	s := New(dispatch)

	// Schedule a task that should fire immediately (RunAt in the past).
	past := time.Now().Add(-time.Second)
	s.AddTask(&ScheduledTask{
		ID:     "fire-now",
		Type:   TaskTypeOneShot,
		Prompt: "do it now",
		UserID: "user-1",
		RunAt:  &past,
	})

	// Schedule a task far in the future (should NOT fire).
	future := time.Now().Add(time.Hour)
	s.AddTask(&ScheduledTask{
		ID:     "fire-later",
		Type:   TaskTypeOneShot,
		Prompt: "not yet",
		UserID: "user-1",
		RunAt:  &future,
	})

	ctx, cancel := context.WithCancel(context.Background())

	go func() {
		_ = s.Run(ctx)
	}()

	// Wait enough for at least one tick.
	time.Sleep(2 * time.Second)
	cancel()

	mu.Lock()
	defer mu.Unlock()

	if len(dispatched) != 1 {
		t.Fatalf("expected 1 dispatched task, got %d", len(dispatched))
	}
	if dispatched[0].ID != "fire-now" {
		t.Errorf("expected dispatched task ID 'fire-now', got %q", dispatched[0].ID)
	}

	// Verify status was updated.
	s.mu.Lock()
	defer s.mu.Unlock()
	if task, ok := s.tasks["fire-now"]; ok {
		if task.Status != "completed" {
			t.Errorf("expected status 'completed', got %q", task.Status)
		}
	}
	if task, ok := s.tasks["fire-later"]; ok {
		if task.Status != "pending" {
			t.Errorf("expected future task status 'pending', got %q", task.Status)
		}
	}
}
