// Package scheduler provides task scheduling with one-shot and cron support.
package scheduler

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

// TaskType distinguishes one-shot from recurring tasks.
type TaskType string

const (
	// TaskTypeOneShot fires once at RunAt time.
	TaskTypeOneShot TaskType = "one_shot"
	// TaskTypeCron fires on a cron schedule.
	TaskTypeCron TaskType = "cron"
)

// ScheduledTask represents a pending or completed scheduled task.
type ScheduledTask struct {
	ID          string
	Type        TaskType
	Prompt      string
	UserID      string
	ChannelID   string
	RunAt       *time.Time // for one-shot tasks
	CronExpr    string     // for cron tasks
	Description string
	Status      string // "pending", "completed", "failed"
	CreatedAt   time.Time
}

// DispatchFunc is called when a task fires.
type DispatchFunc func(context.Context, *ScheduledTask) error

// Scheduler manages scheduled tasks and dispatches them when due.
type Scheduler struct {
	tasks      map[string]*ScheduledTask
	dispatchFn DispatchFunc
	running    bool
	mu         sync.Mutex
	cancel     context.CancelFunc
	done       chan struct{}
}

// New creates a Scheduler with the given dispatch function.
func New(dispatchFn DispatchFunc) *Scheduler {
	return &Scheduler{
		tasks:      make(map[string]*ScheduledTask),
		dispatchFn: dispatchFn,
	}
}

// AddTask adds a task to the scheduler. If the task has no ID, one is generated.
func (s *Scheduler) AddTask(task *ScheduledTask) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if task.ID == "" {
		task.ID = uuid.New().String()
	}
	if task.Status == "" {
		task.Status = "pending"
	}
	if task.CreatedAt.IsZero() {
		task.CreatedAt = time.Now()
	}
	s.tasks[task.ID] = task
}

// RemoveTask removes a task by ID. Returns true if the task existed.
func (s *Scheduler) RemoveTask(id string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	_, ok := s.tasks[id]
	if ok {
		delete(s.tasks, id)
	}
	return ok
}

// ListTasks returns all tasks for a given user. If userID is empty, all tasks
// are returned.
func (s *Scheduler) ListTasks(userID string) []*ScheduledTask {
	s.mu.Lock()
	defer s.mu.Unlock()

	var result []*ScheduledTask
	for _, t := range s.tasks {
		if userID == "" || t.UserID == userID {
			result = append(result, t)
		}
	}
	return result
}

// Run starts the scheduler loop, checking for due tasks every second.
// It blocks until the context is cancelled or Stop is called.
func (s *Scheduler) Run(ctx context.Context) error {
	s.mu.Lock()
	if s.running {
		s.mu.Unlock()
		return fmt.Errorf("scheduler already running")
	}
	ctx, cancel := context.WithCancel(ctx)
	s.cancel = cancel
	s.running = true
	s.done = make(chan struct{})
	s.mu.Unlock()

	defer func() {
		s.mu.Lock()
		s.running = false
		s.mu.Unlock()
		close(s.done)
	}()

	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case now := <-ticker.C:
			s.processDueTasks(ctx, now)
		}
	}
}

// Stop signals the scheduler to stop and waits for it to finish.
func (s *Scheduler) Stop() {
	s.mu.Lock()
	cancel := s.cancel
	done := s.done
	s.mu.Unlock()

	if cancel != nil {
		cancel()
	}
	if done != nil {
		<-done
	}
}

// processDueTasks fires any one-shot tasks whose RunAt has passed.
func (s *Scheduler) processDueTasks(ctx context.Context, now time.Time) {
	s.mu.Lock()
	var due []*ScheduledTask
	for _, t := range s.tasks {
		if t.Type == TaskTypeOneShot && t.Status == "pending" && t.RunAt != nil && !now.Before(*t.RunAt) {
			due = append(due, t)
		}
	}
	s.mu.Unlock()

	for _, t := range due {
		if err := s.dispatchFn(ctx, t); err != nil {
			s.mu.Lock()
			t.Status = "failed"
			s.mu.Unlock()
			continue
		}
		s.mu.Lock()
		t.Status = "completed"
		s.mu.Unlock()
	}
}
