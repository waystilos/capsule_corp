package messaging

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"capsule-corp/internal/sanitize"
)

const (
	MaxBodyLen         = 2000
	MaxEnvelopeBytes   = 64 * 1024
	MaxInboxFiles      = 256
	MaxInboxTotalBytes = 16 * 1024 * 1024
)

type Message struct {
	ID          string    `json:"id"`
	Kind        string    `json:"kind"`
	From        string    `json:"from"`
	To          string    `json:"to"`
	Body        string    `json:"body"`
	EnvelopeSHA string    `json:"envelope_sha,omitempty"`
	SentAt      time.Time `json:"sent_at"`
	Acked       bool      `json:"acked,omitempty"`
}

type AckRecord struct {
	Ack    string    `json:"ack"`
	SentAt time.Time `json:"sent_at"`
}

// agentIDPattern bounds agent IDs that become inbox file names. Must start with an
// alphanumeric (rejects "..", hidden files, and the reserved "_" prefix) and contain no
// path separators.
var agentIDPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`)

// inboxPath validates agentID and returns its inbox file path. A single leading "@"
// (as in `capsule send --to @goku`) is accepted and stripped.
func inboxPath(targetDir, agentID string) (string, string, error) {
	agentID = strings.TrimPrefix(agentID, "@")
	if !agentIDPattern.MatchString(agentID) {
		return "", "", fmt.Errorf("invalid agent id %q: must match %s", agentID, agentIDPattern.String())
	}
	return filepath.Join(targetDir, ".capsule", "inbox", agentID+".jsonl"), agentID, nil
}

func ensureInboxDir(targetDir string) (string, error) {
	inboxDir := filepath.Join(targetDir, ".capsule", "inbox")
	if err := os.MkdirAll(inboxDir, 0755); err != nil {
		return "", err
	}
	return inboxDir, nil
}

func ensureEnvelopeDir(targetDir string) (string, error) {
	envDir := filepath.Join(targetDir, ".capsule", "envelopes")
	if err := os.MkdirAll(envDir, 0755); err != nil {
		return "", err
	}
	return envDir, nil
}

// StoreEnvelope saves envelope content by its sha256 hash if provided.
func StoreEnvelope(targetDir string, envelopeData []byte) (string, error) {
	if len(envelopeData) == 0 {
		return "", nil
	}
	if len(envelopeData) > MaxEnvelopeBytes {
		return "", fmt.Errorf("envelope exceeds maximum allowed size of %d bytes", MaxEnvelopeBytes)
	}
	hash := sha256.Sum256(envelopeData)
	shaHex := hex.EncodeToString(hash[:])

	envDir, err := ensureEnvelopeDir(targetDir)
	if err != nil {
		return "", err
	}
	filePath := filepath.Join(envDir, shaHex+".json")
	if err := os.WriteFile(filePath, envelopeData, 0644); err != nil {
		return "", err
	}
	return shaHex, nil
}

// Send delivers a message to an agent's inbox file.
func Send(targetDir, fromAgent, toAgent, body string, envelopeData []byte) (*Message, error) {
	path, toAgent, err := inboxPath(targetDir, sanitize.Scrub(toAgent, false, false))
	if err != nil {
		return nil, err
	}
	if _, err := ensureInboxDir(targetDir); err != nil {
		return nil, err
	}

	fromAgent = sanitize.Scrub(fromAgent, false, false)

	body = sanitize.Scrub(body, true, false)
	if len(body) > MaxBodyLen {
		body = body[:MaxBodyLen]
	}

	var envSHA string
	if len(envelopeData) > 0 {
		envSHA, err = StoreEnvelope(targetDir, envelopeData)
		if err != nil {
			return nil, err
		}
	}

	idBytes := make([]byte, 8)
	rand.Read(idBytes)
	msgID := "msg_" + hex.EncodeToString(idBytes)

	msg := Message{
		ID:          msgID,
		Kind:        "message",
		From:        fromAgent,
		To:          toAgent,
		Body:        body,
		EnvelopeSHA: envSHA,
		SentAt:      time.Now().UTC(),
	}

	line, err := json.Marshal(msg)
	if err != nil {
		return nil, err
	}

	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0600)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	if _, err := f.Write(append(line, '\n')); err != nil {
		return nil, err
	}

	return &msg, nil
}

// ReadInbox parses all messages and acknowledges in an agent's inbox.
func ReadInbox(targetDir, agentID string, unreadOnly bool) ([]Message, error) {
	path, _, err := inboxPath(targetDir, agentID)
	if err != nil {
		return nil, err
	}
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return []Message{}, nil
	}
	if err != nil {
		return nil, err
	}

	lines := strings.Split(string(data), "\n")
	messages := make(map[string]*Message)
	var orderedIDs []string
	acks := make(map[string]bool)

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		var raw map[string]any
		if err := json.Unmarshal([]byte(line), &raw); err != nil {
			continue
		}
		if ackVal, ok := raw["ack"].(string); ok {
			acks[ackVal] = true
			continue
		}
		var msg Message
		if err := json.Unmarshal([]byte(line), &msg); err == nil && msg.ID != "" {
			messages[msg.ID] = &msg
			orderedIDs = append(orderedIDs, msg.ID)
		}
	}

	results := []Message{}
	for _, id := range orderedIDs {
		m := messages[id]
		m.Acked = acks[id]
		if unreadOnly && m.Acked {
			continue
		}
		results = append(results, *m)
	}

	return results, nil
}

// FindInboxForMessage searches inboxes to locate which agent received a given message ID.
func FindInboxForMessage(targetDir, msgID string) (string, error) {
	inboxDir := filepath.Join(targetDir, ".capsule", "inbox")
	entries, err := os.ReadDir(inboxDir)
	if err != nil {
		return "", err
	}
	for _, e := range entries {
		if strings.HasSuffix(e.Name(), ".jsonl") && !strings.HasPrefix(e.Name(), "_") {
			agent := strings.TrimSuffix(e.Name(), ".jsonl")
			msgs, _ := ReadInbox(targetDir, agent, false)
			for _, m := range msgs {
				if m.ID == msgID {
					return agent, nil
				}
			}
		}
	}
	return "", fmt.Errorf("message %s not found in any inbox", msgID)
}

// Ack appends an acknowledgement for a message ID.
func Ack(targetDir, agentID, msgID string) error {
	if agentID == "" {
		found, err := FindInboxForMessage(targetDir, msgID)
		if err != nil {
			return err
		}
		agentID = found
	} else {
		if _, _, err := inboxPath(targetDir, agentID); err != nil {
			return err
		}
		// Check if message is actually in this agent's inbox, otherwise auto-locate
		msgs, _ := ReadInbox(targetDir, agentID, false)
		hasMsg := false
		for _, m := range msgs {
			if m.ID == msgID {
				hasMsg = true
				break
			}
		}
		if !hasMsg {
			if found, err := FindInboxForMessage(targetDir, msgID); err == nil {
				agentID = found
			}
		}
	}

	path, _, err := inboxPath(targetDir, agentID)
	if err != nil {
		return err
	}
	ackRec := AckRecord{
		Ack:    msgID,
		SentAt: time.Now().UTC(),
	}
	data, err := json.Marshal(ackRec)
	if err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0600)
	if err != nil {
		return err
	}
	defer f.Close()

	_, err = f.Write(append(data, '\n'))
	return err
}

