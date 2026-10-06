package server

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
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
	rec2 := httptest.NewRecorder()
	srv.ServeHTTP(rec2, req2)

	if rec2.Code != http.StatusOK {
		t.Fatalf("route expected 200, got %d", rec2.Code)
	}
}
