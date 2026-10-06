package sanitize

import (
	"testing"
)

func TestScrubANSI(t *testing.T) {
	input := "\x1b[31mRed text\x1b[0m and normal"
	expected := "Red text and normal"
	actual := Scrub(input, true, false)
	if actual != expected {
		t.Fatalf("expected %q, got %q", expected, actual)
	}
}

func TestScrubInvisibleChars(t *testing.T) {
	// Zero-width space U+200B (Cf), Braille Blank U+2800
	input := "Hello\u200BWorld\u2800!"
	expected := "HelloWorld!"
	actual := Scrub(input, true, false)
	if actual != expected {
		t.Fatalf("expected %q, got %q", expected, actual)
	}
}

func TestScrubNewlines(t *testing.T) {
	input := "Line1\nLine2\r\nLine3"
	expectedWithNewlines := "Line1\nLine2\nLine3"
	expectedWithout := "Line1 Line2 Line3"

	if res := Scrub(input, true, false); res != expectedWithNewlines {
		t.Fatalf("expected %q, got %q", expectedWithNewlines, res)
	}
	if res := Scrub(input, false, false); res != expectedWithout {
		t.Fatalf("expected %q, got %q", expectedWithout, res)
	}
}

func TestCap(t *testing.T) {
	input := "Hello World this is a very long string"
	capped := Cap(input, 15, "...")
	if len(capped) > 15 {
		t.Fatalf("length %d exceeded 15: %q", len(capped), capped)
	}
}
