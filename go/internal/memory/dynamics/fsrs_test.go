package dynamics

import (
	"math"
	"testing"
	"time"
)

func TestDefaultParams(t *testing.T) {
	p := DefaultParams()

	if p.RequestRetention != 0.9 {
		t.Errorf("RequestRetention = %v, want 0.9", p.RequestRetention)
	}
	if p.MaxInterval != 365 {
		t.Errorf("MaxInterval = %v, want 365", p.MaxInterval)
	}
	if p.W[20] != 0.1542 {
		t.Errorf("W[20] (decay exponent) = %v, want 0.1542", p.W[20])
	}

	// Factor should be 0.9^(-1/w20) - 1
	expectedFactor := math.Pow(0.9, -1.0/p.W[20]) - 1
	gotFactor := p.factor()
	if math.Abs(gotFactor-expectedFactor) > 1e-10 {
		t.Errorf("factor() = %v, want %v", gotFactor, expectedFactor)
	}

	// All initial stability weights should be positive and increasing
	for i := 0; i < 3; i++ {
		if p.W[i] >= p.W[i+1] {
			t.Errorf("W[%d]=%v should be < W[%d]=%v (stability increases with grade)", i, p.W[i], i+1, p.W[i+1])
		}
	}
}

func TestRetrievability(t *testing.T) {
	params := DefaultParams()
	now := time.Now()

	t.Run("freshly reviewed is approximately 1.0", func(t *testing.T) {
		state := &MemoryState{
			Stability:   5.0,
			Difficulty:  5.0,
			LastReview:  now,
			ReviewCount: 1,
		}
		r := Retrievability(state, now, &params)
		if r < 0.99 || r > 1.0 {
			t.Errorf("Retrievability immediately after review = %v, want ~1.0", r)
		}
	})

	t.Run("at stability days retrievability is about 0.9", func(t *testing.T) {
		stability := 10.0
		state := &MemoryState{
			Stability:   stability,
			Difficulty:  5.0,
			LastReview:  now.Add(-time.Duration(stability*24) * time.Hour),
			ReviewCount: 1,
		}
		r := Retrievability(state, now, &params)
		// By definition, stability is the time for R to drop to 90%
		if math.Abs(r-0.9) > 0.01 {
			t.Errorf("Retrievability at stability days = %v, want ~0.9", r)
		}
	})

	t.Run("old memory has lower retrievability", func(t *testing.T) {
		state := &MemoryState{
			Stability:   5.0,
			Difficulty:  5.0,
			LastReview:  now.Add(-30 * 24 * time.Hour),
			ReviewCount: 1,
		}
		r := Retrievability(state, now, &params)
		if r >= 0.9 {
			t.Errorf("Retrievability after 30 days with stability 5 = %v, want < 0.9", r)
		}
		if r <= 0 {
			t.Errorf("Retrievability after 30 days = %v, want > 0", r)
		}
	})

	t.Run("higher stability decays slower", func(t *testing.T) {
		tenDaysAgo := now.Add(-10 * 24 * time.Hour)

		lowStab := &MemoryState{Stability: 2.0, Difficulty: 5.0, LastReview: tenDaysAgo, ReviewCount: 1}
		highStab := &MemoryState{Stability: 20.0, Difficulty: 5.0, LastReview: tenDaysAgo, ReviewCount: 1}

		rLow := Retrievability(lowStab, now, &params)
		rHigh := Retrievability(highStab, now, &params)

		if rHigh <= rLow {
			t.Errorf("Higher stability should decay slower: rHigh=%v, rLow=%v", rHigh, rLow)
		}
	})

	t.Run("zero review count returns 0", func(t *testing.T) {
		state := &MemoryState{ReviewCount: 0}
		r := Retrievability(state, now, &params)
		if r != 0.0 {
			t.Errorf("Retrievability with no reviews = %v, want 0.0", r)
		}
	})
}

func TestReview(t *testing.T) {
	params := DefaultParams()
	now := time.Now()

	t.Run("first review sets initial state", func(t *testing.T) {
		initial := &MemoryState{}

		for _, grade := range []Grade{GradeAgain, GradeHard, GradeGood, GradeEasy} {
			result := Review(initial, grade, &params, now)

			if result.ReviewCount != 1 {
				t.Errorf("grade %d: ReviewCount = %d, want 1", grade, result.ReviewCount)
			}
			if result.Stability != params.W[int(grade)-1] {
				t.Errorf("grade %d: Stability = %v, want %v", grade, result.Stability, params.W[int(grade)-1])
			}
			if result.Difficulty < 1 || result.Difficulty > 10 {
				t.Errorf("grade %d: Difficulty = %v, want [1, 10]", grade, result.Difficulty)
			}
			if !result.LastReview.Equal(now) {
				t.Errorf("grade %d: LastReview = %v, want %v", grade, result.LastReview, now)
			}
			if result.NextReview.Before(now) {
				t.Errorf("grade %d: NextReview %v is before now %v", grade, result.NextReview, now)
			}
		}
	})

	t.Run("easy grade produces higher stability than hard", func(t *testing.T) {
		// Use stability=10, elapsed=10 days so retrievability is ~0.9 and
		// the grade-dependent bonus/penalty produces a visible difference
		state := &MemoryState{
			Stability:   10.0,
			Difficulty:  5.0,
			LastReview:  now.Add(-10 * 24 * time.Hour),
			ReviewCount: 3,
		}

		hard := Review(state, GradeHard, &params, now)
		easy := Review(state, GradeEasy, &params, now)

		if easy.Stability <= hard.Stability {
			t.Errorf("Easy stability (%v) should be > Hard stability (%v)", easy.Stability, hard.Stability)
		}
	})

	t.Run("again grade does not increase stability", func(t *testing.T) {
		state := &MemoryState{
			Stability:   10.0,
			Difficulty:  5.0,
			LastReview:  now.Add(-5 * 24 * time.Hour),
			ReviewCount: 3,
		}

		result := Review(state, GradeAgain, &params, now)
		if result.Stability > state.Stability {
			t.Errorf("Again should not increase stability: got %v, original %v", result.Stability, state.Stability)
		}
	})

	t.Run("again produces lower stability than good", func(t *testing.T) {
		state := &MemoryState{
			Stability:   10.0,
			Difficulty:  5.0,
			LastReview:  now.Add(-10 * 24 * time.Hour),
			ReviewCount: 3,
		}

		again := Review(state, GradeAgain, &params, now)
		good := Review(state, GradeGood, &params, now)

		if again.Stability >= good.Stability {
			t.Errorf("Again stability (%v) should be < Good stability (%v)", again.Stability, good.Stability)
		}
	})

	t.Run("review count increments", func(t *testing.T) {
		state := &MemoryState{
			Stability:   5.0,
			Difficulty:  5.0,
			LastReview:  now.Add(-24 * time.Hour),
			ReviewCount: 5,
		}

		result := Review(state, GradeGood, &params, now)
		if result.ReviewCount != 6 {
			t.Errorf("ReviewCount = %d, want 6", result.ReviewCount)
		}
	})

	t.Run("next review is in the future", func(t *testing.T) {
		state := &MemoryState{
			Stability:   5.0,
			Difficulty:  5.0,
			LastReview:  now.Add(-2 * 24 * time.Hour),
			ReviewCount: 1,
		}

		result := Review(state, GradeGood, &params, now)
		if !result.NextReview.After(now) {
			t.Errorf("NextReview %v should be after now %v", result.NextReview, now)
		}
	})
}
