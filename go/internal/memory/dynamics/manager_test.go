package dynamics

import (
	"math"
	"testing"
)

func TestCalculateScoreBlending(t *testing.T) {
	// nil db means no FSRS state exists, so retrievability defaults to 0.5
	mgr := NewDynamicsManager(nil)

	tests := []struct {
		name          string
		semanticScore float64
		wantScore     float64
	}{
		{
			name:          "perfect semantic score",
			semanticScore: 1.0,
			// 0.6*1.0 + 0.4*0.5 = 0.8
			wantScore: 0.8,
		},
		{
			name:          "zero semantic score",
			semanticScore: 0.0,
			// 0.6*0.0 + 0.4*0.5 = 0.2
			wantScore: 0.2,
		},
		{
			name:          "mid semantic score",
			semanticScore: 0.5,
			// 0.6*0.5 + 0.4*0.5 = 0.5
			wantScore: 0.5,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			score := mgr.CalculateScore("mem-1", "user-1", tt.semanticScore)
			if math.Abs(score-tt.wantScore) > 1e-10 {
				t.Errorf("CalculateScore = %v, want %v", score, tt.wantScore)
			}
		})
	}
}

func TestCalculateScoreWeights(t *testing.T) {
	mgr := NewDynamicsManager(nil)

	if mgr.semWeight != 0.6 {
		t.Errorf("semWeight = %v, want 0.6", mgr.semWeight)
	}
	if mgr.dynWeight != 0.4 {
		t.Errorf("dynWeight = %v, want 0.4", mgr.dynWeight)
	}
	if mgr.semWeight+mgr.dynWeight != 1.0 {
		t.Errorf("weights should sum to 1.0, got %v", mgr.semWeight+mgr.dynWeight)
	}
}

func TestNewMemoryDefaultState(t *testing.T) {
	mgr := NewDynamicsManager(nil)

	// A new memory (no DB state) should get a reasonable blended score
	score := mgr.CalculateScore("new-memory", "user-1", 0.8)

	// 0.6*0.8 + 0.4*0.5 = 0.68
	expected := 0.68
	if math.Abs(score-expected) > 1e-10 {
		t.Errorf("New memory score = %v, want %v", score, expected)
	}

	// Score should be between 0 and 1 for valid inputs
	if score < 0 || score > 1 {
		t.Errorf("Score = %v, want [0, 1]", score)
	}
}

func TestNewDynamicsManagerDefaults(t *testing.T) {
	mgr := NewDynamicsManager(nil)

	if mgr.params == nil {
		t.Fatal("params should not be nil")
	}
	if mgr.params.RequestRetention != 0.9 {
		t.Errorf("RequestRetention = %v, want 0.9", mgr.params.RequestRetention)
	}
}
