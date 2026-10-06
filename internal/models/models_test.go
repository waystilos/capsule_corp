package models

import (
	"os"
	"testing"
)

func TestResolveModelPrecedence(t *testing.T) {
	// 1. Explicit model flag wins
	res := ResolveModel("goku", "flash", "gpt-4o", "", "")
	if res.Model != "gpt-4o" {
		t.Fatalf("expected gpt-4o, got %s", res.Model)
	}

	// 2. Env variable wins over config
	os.Setenv("CAPSULE_MODEL", "claude-3-opus")
	defer os.Unsetenv("CAPSULE_MODEL")
	res = ResolveModel("goku", "flash", "", "", "")
	if res.Model != "claude-3-opus" {
		t.Fatalf("expected claude-3-opus, got %s", res.Model)
	}
	os.Unsetenv("CAPSULE_MODEL")

	// 3. Protected bot escalation: Android-17 on flash escalates to pro
	res = ResolveModel("android-17", "flash", "", "", "")
	if res.Tier != "pro" || !res.Escalated {
		t.Fatalf("expected android-17 to escalate to pro, got tier=%s, escalated=%v", res.Tier, res.Escalated)
	}

	// 4. Security prompt escalation: flash escalates to pro
	res = ResolveModel("goku", "flash", "", "Fix CVE-2024-1234 vulnerability and leak", "")
	if res.Tier != "pro" || !res.Escalated {
		t.Fatalf("expected prompt escalation to pro, got tier=%s, escalated=%v", res.Tier, res.Escalated)
	}

	// 5. Normal flash tier resolution
	res = ResolveModel("goku", "flash", "", "Typo fix in docs", "")
	if res.Model != "haiku" || res.Tier != "flash" {
		t.Fatalf("expected haiku / flash, got model=%s tier=%s", res.Model, res.Tier)
	}
}
