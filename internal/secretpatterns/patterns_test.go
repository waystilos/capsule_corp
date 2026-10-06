package secretpatterns

import (
	"testing"
)

func TestScanTextDetected(t *testing.T) {
	sample := "\nsome config\nAWS_KEY=" + "AKIA" + "IOSFODNN7EXAMPLE\nOPENAI_KEY=" + "sk-" + "abcdef1234567890abcdef123456\n"
	matches := ScanText(sample)
	if len(matches) == 0 {
		t.Fatal("expected at least one secret match")
	}
	foundOpenAI := false
	for _, m := range matches {
		if m.Rule == "OpenAI / Service Secret Key" {
			foundOpenAI = true
		}
	}
	if !foundOpenAI {
		t.Errorf("expected OpenAI key match, got: %+v", matches)
	}
}

func TestScanDiffMergeConflict(t *testing.T) {
	diff := `
+<<<<<<< HEAD
+int a = 1;
+=======
+int a = 2;
+>>>>>>> branch
`
	matches := ScanDiff(diff)
	if len(matches) < 3 {
		t.Fatalf("expected 3 merge conflict matches, got %d", len(matches))
	}
}

func TestShannonEntropy(t *testing.T) {
	lowEntropy := "aaaaaaaaaaaaaaaa"
	highEntropy := "8fG#k2$mZ9!qL0*w"

	low := ShannonEntropy(lowEntropy)
	high := ShannonEntropy(highEntropy)

	if low >= high {
		t.Fatalf("expected high entropy (%f) > low entropy (%f)", high, low)
	}
}
