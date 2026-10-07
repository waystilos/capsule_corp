package server

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func TestServerHealth(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "srv_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	srv, err := NewServer(tmpDir, "")
	if err != nil {
		t.Fatalf("NewServer failed: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()
	srv.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}

	var res map[string]string
	_ = json.NewDecoder(rec.Body).Decode(&res)
	if res["status"] != "ok" {
		t.Fatalf("expected status ok, got: %v", res)
	}
}

func TestServerClockInAndRoute(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "srv_test_*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	srv, err := NewServer(tmpDir, "")
	if err != nil {
		t.Fatalf("NewServer failed: %v", err)
	}

	// 1. Clock in via POST /api/v1/room/clock-in
	cinPayload := ClockInRequest{
		AgentID: "goku",
		Role:    "Builder",
		Task:    "Implement feature via service",
		Files:   []string{"main.go"},
	}
	body, _ := json.Marshal(cinPayload)
	req := httptest.NewRequest(http.MethodPost, "/api/v1/room/clock-in", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	srv.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("clock-in expected 200, got %d (body: %s)", rec.Code, rec.Body.String())
	}

	// 2. Route via POST /api/v1/route
	routePayload := RouteRequestPayload{
		Task: "Implement the login controller in Go",
	}
	routeBody, _ := json.Marshal(routePayload)
	req2 := httptest.NewRequest(http.MethodPost, "/api/v1/route", bytes.NewReader(routeBody))
	req2.Header.Set("Content-Type", "application/json")
	rec2 := httptest.NewRecorder()
	srv.ServeHTTP(rec2, req2)

	if rec2.Code != http.StatusOK {
		t.Fatalf("route expected 200, got %d", rec2.Code)
	}
}

func newTestServer(t *testing.T) *Server {
	t.Helper()
	srv, err := NewServer(t.TempDir(), "")
	if err != nil {
		t.Fatalf("NewServer failed: %v", err)
	}
	return srv
}

func postJSON(t *testing.T, srv *Server, path string, payload any) *httptest.ResponseRecorder {
	t.Helper()
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, path, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	srv.ServeHTTP(rec, req)
	return rec
}

func clockIn(t *testing.T, srv *Server, agent, file string) (shiftID, token string) {
	t.Helper()
	rec := postJSON(t, srv, "/api/v1/room/clock-in", ClockInRequest{AgentID: agent, Task: "t", Files: []string{file}})
	if rec.Code != http.StatusOK {
		t.Fatalf("clock-in expected 200, got %d (%s)", rec.Code, rec.Body.String())
	}
	var res struct {
		Shift struct {
			ShiftID string `json:"shift_id"`
		} `json:"shift"`
		SessionToken string `json:"session_token"`
	}
	_ = json.NewDecoder(rec.Body).Decode(&res)
	if res.Shift.ShiftID == "" || res.SessionToken == "" {
		t.Fatalf("clock-in missing shift_id or session_token: %+v", res)
	}
	return res.Shift.ShiftID, res.SessionToken
}

func TestClockOutAndHeartbeatRequireSessionToken(t *testing.T) {
	srv := newTestServer(t)
	shiftID, token := clockIn(t, srv, "victim", "a.go")

	// Knowing only the shift_id (visible to anyone via GET /api/v1/room) must not be enough.
	for _, path := range []string{"/api/v1/room/heartbeat", "/api/v1/room/clock-out"} {
		for name, payload := range map[string]any{
			"shift_id only":  map[string]string{"session_id": shiftID, "agent_id": "attacker"},
			"wrong token":    map[string]string{"session_token": "deadbeef"},
			"missing fields": map[string]string{},
		} {
			rec := postJSON(t, srv, path, payload)
			if rec.Code != http.StatusUnauthorized {
				t.Errorf("%s with %s: expected 401, got %d (%s)", path, name, rec.Code, rec.Body.String())
			}
		}
	}

	// The token returned by clock-in is what the owner passes back.
	if rec := postJSON(t, srv, "/api/v1/room/heartbeat", map[string]string{"session_token": token}); rec.Code != http.StatusOK {
		t.Fatalf("heartbeat with valid token expected 200, got %d (%s)", rec.Code, rec.Body.String())
	}
	if rec := postJSON(t, srv, "/api/v1/room/clock-out", map[string]string{"session_token": token, "summary": "done"}); rec.Code != http.StatusOK {
		t.Fatalf("clock-out with valid token expected 200, got %d (%s)", rec.Code, rec.Body.String())
	}
	// Token is single-use: the shift is gone.
	if rec := postJSON(t, srv, "/api/v1/room/clock-out", map[string]string{"session_token": token}); rec.Code != http.StatusUnauthorized {
		t.Fatalf("reused token expected 401, got %d", rec.Code)
	}
}

func TestClockOutTokenOnlyClosesOwnShift(t *testing.T) {
	srv := newTestServer(t)
	_, tokenA := clockIn(t, srv, "agent-a", "a.go")
	shiftB, _ := clockIn(t, srv, "agent-b", "b.go")

	if rec := postJSON(t, srv, "/api/v1/room/clock-out", map[string]string{"session_token": tokenA}); rec.Code != http.StatusOK {
		t.Fatalf("clock-out A expected 200, got %d", rec.Code)
	}
	req := httptest.NewRequest(http.MethodGet, "/api/v1/room", nil)
	rec := httptest.NewRecorder()
	srv.ServeHTTP(rec, req)
	var rd struct {
		ActiveShifts map[string]any `json:"active_shifts"`
	}
	_ = json.NewDecoder(rec.Body).Decode(&rd)
	if _, ok := rd.ActiveShifts[shiftB]; !ok || len(rd.ActiveShifts) != 1 {
		t.Fatalf("expected only agent-b's shift to remain, got %v", rd.ActiveShifts)
	}
}

func TestPostRejectsNonJSONContentType(t *testing.T) {
	srv := newTestServer(t)
	paths := []string{
		"/api/v1/room/clock-in", "/api/v1/room/clock-out", "/api/v1/room/heartbeat",
		"/api/v1/messages", "/api/v1/messages/ack", "/api/v1/route",
	}
	// text/plain and form posts are "simple" cross-origin requests a web page can send without CORS preflight.
	for _, ct := range []string{"text/plain", "application/x-www-form-urlencoded", ""} {
		for _, p := range paths {
			req := httptest.NewRequest(http.MethodPost, p, strings.NewReader(`{"to":"goku","body":"x","task":"x"}`))
			if ct != "" {
				req.Header.Set("Content-Type", ct)
			}
			rec := httptest.NewRecorder()
			srv.ServeHTTP(rec, req)
			if rec.Code != http.StatusUnsupportedMediaType {
				t.Errorf("POST %s with Content-Type %q: expected 415, got %d", p, ct, rec.Code)
			}
		}
	}
	// application/json with charset is fine.
	req := httptest.NewRequest(http.MethodPost, "/api/v1/route", strings.NewReader(`{"task":"fix typo"}`))
	req.Header.Set("Content-Type", "application/json; charset=utf-8")
	rec := httptest.NewRecorder()
	srv.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("application/json; charset=utf-8 expected 200, got %d", rec.Code)
	}
}

func TestSendMessageRejectsTraversal(t *testing.T) {
	srv := newTestServer(t)
	rec := postJSON(t, srv, "/api/v1/messages", SendMessageRequest{From: "a", To: "../../evil", Body: "x"})
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d (%s)", rec.Code, rec.Body.String())
	}
	req := httptest.NewRequest(http.MethodGet, "/api/v1/inbox/..%2F..%2Fetc", nil)
	rec = httptest.NewRecorder()
	srv.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("inbox traversal expected 400, got %d (%s)", rec.Code, rec.Body.String())
	}
}

func TestInboxEmptyReturnsArray(t *testing.T) {
	srv := newTestServer(t)
	req := httptest.NewRequest(http.MethodGet, "/api/v1/inbox/goku?unread=true", nil)
	rec := httptest.NewRecorder()
	srv.ServeHTTP(rec, req)
	if !strings.Contains(rec.Body.String(), `"messages":[]`) {
		t.Fatalf("expected \"messages\":[], got %s", rec.Body.String())
	}

	sent := postJSON(t, srv, "/api/v1/messages", SendMessageRequest{From: "a", To: "goku", Body: "x"})
	var msg struct {
		ID string `json:"id"`
	}
	_ = json.NewDecoder(sent.Body).Decode(&msg)
	postJSON(t, srv, "/api/v1/messages/ack", AckRequest{AgentID: "goku", MessageID: msg.ID})

	req = httptest.NewRequest(http.MethodGet, "/api/v1/inbox/goku?unread=true", nil)
	rec = httptest.NewRecorder()
	srv.ServeHTTP(rec, req)
	if !strings.Contains(rec.Body.String(), `"messages":[]`) {
		t.Fatalf("after ack expected \"messages\":[], got %s", rec.Body.String())
	}
}
