package recipe

import (
	"encoding/json"
	"testing"
)

func TestParseValidRecipe(t *testing.T) {
	data := `{
		"trial_id": "trial-001",
		"faults": [
			{
				"id": "fault-1",
				"fault_plane": "environmental",
				"fault_model": "network_delay",
				"target": {
					"node": "zk1",
					"interface": "eth0"
				},
				"timing": {
					"duration_s": 10
				},
				"params": {
					"delay_ms": 100
				}
			}
		]
	}`

	var r Recipe
	if err := json.Unmarshal([]byte(data), &r); err != nil {
		t.Fatalf("failed to parse valid recipe: %v", err)
	}

	if r.TrialID != "trial-001" {
		t.Errorf("expected trial_id 'trial-001', got '%s'", r.TrialID)
	}

	if len(r.Faults) != 1 {
		t.Fatalf("expected 1 fault, got %d", len(r.Faults))
	}

	f := r.Faults[0]
	if f.ID != "fault-1" {
		t.Errorf("expected fault id 'fault-1', got '%s'", f.ID)
	}
	if f.FaultPlane != "environmental" {
		t.Errorf("expected fault_plane 'environmental', got '%s'", f.FaultPlane)
	}
	if f.FaultModel != "network_delay" {
		t.Errorf("expected fault_model 'network_delay', got '%s'", f.FaultModel)
	}
	if f.Target.Node != "zk1" {
		t.Errorf("expected target node 'zk1', got '%s'", f.Target.Node)
	}
	if f.Params.DelayMs == nil || *f.Params.DelayMs != 100 {
		t.Errorf("expected delay_ms 100, got %v", f.Params.DelayMs)
	}
}

func TestParseEmptyFaults(t *testing.T) {
	data := `{"trial_id": "trial-002", "faults": []}`

	var r Recipe
	if err := json.Unmarshal([]byte(data), &r); err != nil {
		t.Fatalf("failed to parse recipe with empty faults: %v", err)
	}

	if r.TrialID != "trial-002" {
		t.Errorf("expected trial_id 'trial-002', got '%s'", r.TrialID)
	}
	if len(r.Faults) != 0 {
		t.Errorf("expected 0 faults, got %d", len(r.Faults))
	}
}

func TestParseMultipleFaults(t *testing.T) {
	data := `{
		"trial_id": "trial-003",
		"faults": [
			{
				"id": "fault-1",
				"fault_plane": "environmental",
				"fault_model": "network_delay",
				"target": {"node": "zk1", "interface": "eth0"},
				"timing": {"duration_s": 10},
				"params": {"delay_ms": 100}
			},
			{
				"id": "fault-2",
				"fault_plane": "environmental",
				"fault_model": "disk_slowdown",
				"target": {"node": "zk2"},
				"timing": {"duration_s": 5},
				"params": {"delay_ms": 50}
			}
		]
	}`

	var r Recipe
	if err := json.Unmarshal([]byte(data), &r); err != nil {
		t.Fatalf("failed to parse recipe with multiple faults: %v", err)
	}

	if len(r.Faults) != 2 {
		t.Fatalf("expected 2 faults, got %d", len(r.Faults))
	}

	if r.Faults[0].Target.Node != "zk1" {
		t.Errorf("expected first fault node 'zk1', got '%s'", r.Faults[0].Target.Node)
	}
	if r.Faults[1].Target.Node != "zk2" {
		t.Errorf("expected second fault node 'zk2', got '%s'", r.Faults[1].Target.Node)
	}
}
