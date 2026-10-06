package routing

import (
	"strings"
	"testing"

	"capsule-corp/internal/registry"
)

func TestRouteTask(t *testing.T) {
	reg, _ := registry.LoadRegistry("")

	// 1. Security prompt -> android-17
	dec := RouteTask("We have a leaked api key vulnerability in the login handler", "", reg)
	if dec.Bot != "android-17" {
		t.Fatalf("expected android-17 for leaked api key, got %s", dec.Bot)
	}

	// 2. Implementation prompt -> goku
	dec = RouteTask("implement the new user profile feature and fix tests", "", reg)
	if dec.Bot != "goku" {
		t.Fatalf("expected goku for implementation, got %s", dec.Bot)
	}

	// 3. Verification prompt -> trunks
	dec = RouteTask("verify regression test suite across all gates", "", reg)
	if dec.Bot != "trunks" {
		t.Fatalf("expected trunks for verification, got %s", dec.Bot)
	}

	// 4. Code inquisition -> beerus
	dec = RouteTask("grill me on this architecture and test edge cases", "", reg)
	if dec.Bot != "beerus" {
		t.Fatalf("expected beerus for grill me, got %s", dec.Bot)
	}
}

func TestRenderEnvelope(t *testing.T) {
	env := &TaskEnvelope{
		RootRequest:        "Add auth endpoint",
		Goal:               "Support JWT auth",
		Scope:              []string{"auth.go"},
		AcceptanceCriteria: []string{"JWT validation passes", "Invalid tokens return 401"},
		Verification:       []string{"capsule check"},
	}

	md := RenderMarkdown(env)
	if !strings.Contains(md, "Task Brief Envelope") || !strings.Contains(md, "Support JWT auth") {
		t.Fatalf("invalid envelope markdown render: %s", md)
	}

	hash, err := HashEnvelope(env)
	if err != nil || len(hash) != 64 {
		t.Fatalf("expected 64-char hex hash, got %s (err: %v)", hash, err)
	}
}
