package dynamics

import (
	"math"
	"time"
)

// Grade represents review quality (FSRS-6 rating).
type Grade int

const (
	GradeAgain Grade = 1
	GradeHard  Grade = 2
	GradeGood  Grade = 3
	GradeEasy  Grade = 4
)

// MemoryState holds FSRS state for a memory.
type MemoryState struct {
	Stability   float64
	Difficulty  float64
	LastReview  time.Time
	NextReview  time.Time
	ReviewCount int
}

// FsrsParams holds FSRS-6 parameters.
//
// 21 weights (w[0..20]) control various aspects of the scheduling:
//   - w[0-3]: Initial stability for grades Again/Hard/Good/Easy
//   - w[4-5]: Initial difficulty parameters
//   - w[6-8]: Stability increase factors (success)
//   - w[9]:   Hard penalty multiplier
//   - w[10]:  Easy bonus multiplier
//   - w[11]:  Difficulty update delta
//   - w[13]:  Difficulty mean reversion weight
//   - w[14-17]: Stability after lapse (failure) parameters
//   - w[20]:  Power-law decay exponent for retrievability
type FsrsParams struct {
	W                [21]float64 // FSRS-6 weights
	RequestRetention float64     // Target retention (default 0.9)
	MaxInterval      float64     // Max interval in days (default 365)
}

// DefaultParams returns the default FSRS-6 parameters, aligned with the
// Python implementation in mypalclara/core/memory/dynamics/fsrs.py.
func DefaultParams() FsrsParams {
	return FsrsParams{
		W: [21]float64{
			0.212,   // w[0]:  Initial stability for Again
			1.2931,  // w[1]:  Initial stability for Hard
			2.3065,  // w[2]:  Initial stability for Good
			8.2956,  // w[3]:  Initial stability for Easy
			6.4133,  // w[4]:  Initial difficulty mean
			0.8334,  // w[5]:  Initial difficulty modifier
			3.0194,  // w[6]:  Stability increase base (exp)
			0.001,   // w[7]:  Stability increase exponent (S^-w[7])
			1.8722,  // w[8]:  Retrievability factor in stability growth
			0.1666,  // w[9]:  Hard penalty (< 1)
			0.796,   // w[10]: Easy bonus (> 1... note: actual > 1 effect comes from formula)
			1.4835,  // w[11]: Difficulty delta multiplier
			0.0614,  // w[12]: (unused in core formulas)
			0.2629,  // w[13]: Difficulty mean reversion weight
			1.6483,  // w[14]: Lapse stability multiplier
			0.6014,  // w[15]: Lapse difficulty exponent
			1.8729,  // w[16]: Lapse stability exponent
			0.5425,  // w[17]: Lapse retrievability factor
			0.0912,  // w[18]: (reserved)
			0.0658,  // w[19]: (reserved)
			0.1542,  // w[20]: Power-law decay exponent
		},
		RequestRetention: 0.9,
		MaxInterval:      365,
	}
}

// factor computes the decay factor from w[20] and target retention (0.9).
// Derived from: R(S) = 0.9 -> (1 + factor)^(-w20) = 0.9
// -> factor = 0.9^(-1/w20) - 1
func (p *FsrsParams) factor() float64 {
	return math.Pow(p.RequestRetention, -1.0/p.W[20]) - 1.0
}

// Retrievability calculates the current probability of recall given elapsed time.
// Formula: R = (1 + factor * elapsed_days / stability) ^ (-w[20])
func Retrievability(state *MemoryState, now time.Time, params *FsrsParams) float64 {
	if state.ReviewCount == 0 {
		return 0.0
	}

	elapsed := now.Sub(state.LastReview).Hours() / 24.0
	if elapsed <= 0 {
		return 1.0
	}
	if state.Stability <= 0 {
		return 0.0
	}

	f := params.factor()
	r := math.Pow(1.0+f*elapsed/state.Stability, -params.W[20])
	return clamp(r, 0.0, 1.0)
}

// Review updates memory state after a review, returning a new MemoryState.
func Review(state *MemoryState, grade Grade, params *FsrsParams, now time.Time) *MemoryState {
	newState := &MemoryState{
		LastReview:  now,
		ReviewCount: state.ReviewCount + 1,
	}

	if state.ReviewCount == 0 {
		// First review: use initial stability and difficulty formulas
		newState.Stability = initialStability(grade, params)
		newState.Difficulty = initialDifficulty(grade, params)
	} else {
		// Subsequent reviews
		r := Retrievability(state, now, params)
		newState.Difficulty = nextDifficulty(state.Difficulty, grade, params)
		newState.Stability = nextStability(state.Stability, state.Difficulty, r, grade, params)
	}

	// Calculate next review interval
	interval := nextInterval(newState.Stability, params)
	newState.NextReview = now.Add(time.Duration(interval*24) * time.Hour)

	return newState
}

// initialStability returns w[grade-1] for a first review.
func initialStability(grade Grade, params *FsrsParams) float64 {
	return params.W[int(grade)-1]
}

// initialDifficulty computes D0 = w[4] - exp(w[5] * (grade - 1)) + 1, clamped to [1, 10].
func initialDifficulty(grade Grade, params *FsrsParams) float64 {
	d0 := params.W[4] - math.Exp(params.W[5]*float64(grade-1)) + 1
	return clamp(d0, 1.0, 10.0)
}

// nextDifficulty updates difficulty after a review using mean reversion.
// D' = w[13] * D0_mean + (1 - w[13]) * (D + w[11] * (grade - 3))
func nextDifficulty(d float64, grade Grade, params *FsrsParams) float64 {
	delta := params.W[11] * float64(grade-3)
	adjusted := d + delta
	// Mean reversion toward w[4] (initial difficulty mean)
	newD := params.W[13]*params.W[4] + (1-params.W[13])*adjusted
	return clamp(newD, 1.0, 10.0)
}

// nextStability calculates the new stability after a review.
func nextStability(s, d, r float64, grade Grade, params *FsrsParams) float64 {
	if grade == GradeAgain {
		return stabilityAfterFailure(s, d, r, params)
	}
	return stabilityAfterSuccess(s, d, r, grade, params)
}

// stabilityAfterSuccess computes new stability for grades Hard/Good/Easy.
// S' = S * (1 + exp(w[6]) * (11-D) * S^(-w[7]) * (exp(w[8]*(1-R)) - 1) * bonus)
func stabilityAfterSuccess(s, d, r float64, grade Grade, params *FsrsParams) float64 {
	var bonus float64
	switch grade {
	case GradeHard:
		bonus = params.W[9]
	case GradeGood:
		bonus = 1.0
	case GradeEasy:
		bonus = params.W[10]
	}

	stabilityFactor := math.Exp(params.W[6])
	difficultyFactor := 11 - d
	stabilityDecay := math.Pow(s, -params.W[7])
	retrievabilityFactor := math.Exp(params.W[8]*(1-r)) - 1

	growth := stabilityFactor * difficultyFactor * stabilityDecay * retrievabilityFactor * bonus
	newS := s * (1 + growth)

	return math.Max(0.1, newS)
}

// stabilityAfterFailure computes new stability after a lapse (grade Again).
// S' = w[14] * D^(-w[15]) * ((S+1)^w[16] - 1) * exp(w[17] * (1-R))
func stabilityAfterFailure(s, d, r float64, params *FsrsParams) float64 {
	difficultyFactor := math.Pow(d, -params.W[15])
	stabilityFactor := math.Pow(s+1, params.W[16]) - 1
	retrievabilityFactor := math.Exp(params.W[17] * (1 - r))

	newS := params.W[14] * difficultyFactor * stabilityFactor * retrievabilityFactor

	// Don't increase stability on failure; floor at 0.1
	return math.Max(0.1, math.Min(newS, s))
}

// nextInterval computes the interval (in days) for target retention.
// Derived from solving R(interval) = RequestRetention:
//
//	(1 + factor * interval/S)^(-w20) = R_target
//	interval = S / factor * (R_target^(-1/w20) - 1)
func nextInterval(stability float64, params *FsrsParams) float64 {
	f := params.factor()
	if f == 0 {
		return 1
	}
	interval := stability / f * (math.Pow(params.RequestRetention, -1.0/params.W[20]) - 1)
	return math.Min(math.Max(interval, 1), params.MaxInterval)
}

func clamp(v, lo, hi float64) float64 {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}
