package doctor

import (
	"os"
	"testing"
)

func TestDiagnoseEnvironment(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}

	rep := DiagnoseEnvironment(wd)
	if len(rep.Items) == 0 {
		t.Fatal("expected diagnostic items")
	}
	if !rep.Healthy {
		t.Fatalf("expected healthy report in active environment: %+v", rep)
	}
}
