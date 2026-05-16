package recipe

// FaultTarget describes where a fault should be applied.
type FaultTarget struct {
	Node        string `json:"node"`
	Component   string `json:"component,omitempty"`
	Interface   string `json:"interface,omitempty"`
	InjectionID *int   `json:"injection_id,omitempty"`
}

// FaultTiming describes when a fault should be applied.
type FaultTiming struct {
	Occurrence  *int    `json:"occurrence,omitempty"`
	Phase       string  `json:"phase,omitempty"`
	StartAfterS float64 `json:"start_after_s,omitempty"`
	DurationS   float64 `json:"duration_s"`
}

// FaultParams holds fault-specific parameters.
type FaultParams struct {
	DelayMs       *int    `json:"delay_ms,omitempty"`
	LossPct       *float64 `json:"loss_pct,omitempty"`
	ExceptionClass string `json:"exception_class,omitempty"`
}

// Fault describes a single fault in a trial recipe.
type Fault struct {
	ID         string       `json:"id"`
	FaultPlane string       `json:"fault_plane"`
	FaultModel string       `json:"fault_model"`
	Target     FaultTarget  `json:"target"`
	Timing     FaultTiming  `json:"timing"`
	Params     FaultParams  `json:"params,omitempty"`
}

// Recipe describes a complete trial with zero or more faults.
type Recipe struct {
	TrialID string  `json:"trial_id"`
	Faults  []Fault `json:"faults"`
}
