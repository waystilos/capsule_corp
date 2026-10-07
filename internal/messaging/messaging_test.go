package messaging

import (
	"os"
	"path/filepath"
	"testing"
)

func TestMessagingFlow(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "capsule_msg_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	// Send message
	msg, err := Send(tmpDir, "goku", "trunks", "Verify this commit please", []byte(`{"task": "verify"}`))
	if err != nil {
		t.Fatalf("Send failed: %v", err)
	}
	if msg.EnvelopeSHA == "" {
		t.Fatal("expected envelope sha")
	}

	// Read inbox unread
	msgs, err := ReadInbox(tmpDir, "trunks", true)
	if err != nil {
		t.Fatalf("ReadInbox failed: %v", err)
	}
	if len(msgs) != 1 {
		t.Fatalf("expected 1 unread message, got %d", len(msgs))
	}
	if msgs[0].ID != msg.ID {
		t.Fatalf("expected message id %s, got %s", msg.ID, msgs[0].ID)
	}

	// Ack message
	if err := Ack(tmpDir, "trunks", msg.ID); err != nil {
		t.Fatalf("Ack failed: %v", err)
	}

	// Check unread again: should be 0
	unreads, err := ReadInbox(tmpDir, "trunks", true)
	if err != nil {
		t.Fatalf("ReadInbox unread failed: %v", err)
	}
	if len(unreads) != 0 {
		t.Fatalf("expected 0 unread messages, got %d", len(unreads))
	}

	// Read all: should be 1 and marked acked
	all, err := ReadInbox(tmpDir, "trunks", false)
	if err != nil {
		t.Fatalf("ReadInbox all failed: %v", err)
	}
	if len(all) != 1 || !all[0].Acked {
		t.Fatalf("expected 1 acked message, got %+v", all)
	}
}

func TestUnsafeAgentIDsRejected(t *testing.T) {
	tmpDir := t.TempDir()
	targetDir := filepath.Join(tmpDir, "project")
	if err := os.MkdirAll(targetDir, 0755); err != nil {
		t.Fatal(err)
	}

	bad := []string{"../../evil", "../evil", "a/b", `a\b`, "..", ".hidden", "_handoffs", "/abs", ""}
	for _, id := range bad {
		if _, err := Send(targetDir, "goku", id, "x", nil); err == nil {
			t.Errorf("Send(to=%q) expected error, got nil", id)
		}
		if _, err := ReadInbox(targetDir, id, false); err == nil {
			t.Errorf("ReadInbox(%q) expected error, got nil", id)
		}
	}
	if err := Ack(targetDir, "../../evil", "msg_x"); err == nil {
		t.Error("Ack(agent=../../evil) expected error, got nil")
	}

	// Nothing may be written outside .capsule/inbox.
	for _, p := range []string{filepath.Join(targetDir, "evil.jsonl"), filepath.Join(tmpDir, "evil.jsonl")} {
		if _, err := os.Stat(p); err == nil {
			t.Fatalf("traversal wrote file outside inbox: %s", p)
		}
	}
}

func TestSafeAgentIDsAccepted(t *testing.T) {
	tmpDir := t.TempDir()
	for _, id := range []string{"goku", "android-17", "dr_gero", "john.doe", "Claude"} {
		if _, err := Send(tmpDir, "x", id, "hi", nil); err != nil {
			t.Errorf("Send(to=%q) unexpected error: %v", id, err)
		}
	}
	// A leading @ (as in `capsule send --to @goku`) addresses the same inbox.
	if _, err := Send(tmpDir, "x", "@goku", "hi", nil); err != nil {
		t.Fatalf("Send(to=@goku) unexpected error: %v", err)
	}
	msgs, err := ReadInbox(tmpDir, "goku", false)
	if err != nil {
		t.Fatal(err)
	}
	if len(msgs) != 2 {
		t.Fatalf("expected 2 messages in goku inbox, got %d", len(msgs))
	}
}

func TestReadInboxEmptyIsNonNil(t *testing.T) {
	tmpDir := t.TempDir()
	msg, err := Send(tmpDir, "goku", "trunks", "hi", nil)
	if err != nil {
		t.Fatal(err)
	}
	if err := Ack(tmpDir, "trunks", msg.ID); err != nil {
		t.Fatal(err)
	}
	unread, err := ReadInbox(tmpDir, "trunks", true)
	if err != nil {
		t.Fatal(err)
	}
	if unread == nil {
		t.Fatal("expected empty non-nil slice (JSON []), got nil (JSON null)")
	}
}
