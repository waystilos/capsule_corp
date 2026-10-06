package messaging

import (
	"os"
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
