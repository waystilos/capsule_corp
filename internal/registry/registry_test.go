package registry

import (
	"strings"
	"testing"
)

func TestLoadRegistryEmbedded(t *testing.T) {
	reg, err := LoadRegistry("")
	if err != nil {
		t.Fatalf("LoadRegistry failed: %v", err)
	}
	if len(reg.Bots) == 0 {
		t.Fatal("expected bots in registry, got 0")
	}

	bulma, ok := reg.FindBot("@Bulma")
	if !ok || bulma == nil {
		t.Fatal("expected @Bulma in registry")
	}
	if !strings.Contains(bulma.Role, "Product") {
		t.Fatalf("expected Bulma role to contain 'Product', got %q", bulma.Role)
	}

	goku, ok := reg.FindBot("goku")
	if !ok || goku == nil {
		t.Fatal("expected goku in registry")
	}
	if !strings.Contains(goku.Role, "Frontline") {
		t.Fatalf("expected Goku role to contain 'Frontline', got %q", goku.Role)
	}
}
