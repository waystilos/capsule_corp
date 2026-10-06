package server

import (
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"capsule-corp/internal/messaging"
	"capsule-corp/internal/registry"
	"capsule-corp/internal/room"
	"capsule-corp/internal/routing"
)

type Server struct {
	TargetDir    string
	ResourceRoot string
	Registry     *registry.Registry
	Mux          *http.ServeMux
}

func NewServer(targetDir, resourceRoot string) (*Server, error) {
	reg, err := registry.LoadRegistry(resourceRoot)
	if err != nil {
		return nil, err
	}
	s := &Server{
		TargetDir:    targetDir,
		ResourceRoot: resourceRoot,
		Registry:     reg,
		Mux:          http.NewServeMux(),
	}
	s.routes()
	return s, nil
}

func (s *Server) routes() {
	s.Mux.HandleFunc("/health", s.handleHealth)
	s.Mux.HandleFunc("/api/v1/health", s.handleHealth)
	s.Mux.HandleFunc("/api/v1/room", s.handleRoom)
	s.Mux.HandleFunc("/api/v1/room/clock-in", s.handleClockIn)
	s.Mux.HandleFunc("/api/v1/room/clock-out", s.handleClockOut)
	s.Mux.HandleFunc("/api/v1/room/heartbeat", s.handleHeartbeat)
	s.Mux.HandleFunc("/api/v1/inbox/", s.handleInbox)
	s.Mux.HandleFunc("/api/v1/messages", s.handleSendMessage)
	s.Mux.HandleFunc("/api/v1/messages/ack", s.handleAckMessage)
	s.Mux.HandleFunc("/api/v1/route", s.handleRoute)
	s.Mux.HandleFunc("/api/v1/bots", s.handleBots)
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.Mux.ServeHTTP(w, r)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	respondJSON(w, http.StatusOK, map[string]any{
		"status": "ok",
		"time":   time.Now().UTC().Format(time.RFC3339),
	})
}

func (s *Server) handleRoom(w http.ResponseWriter, r *http.Request) {
	rd, err := room.LoadRoomData(s.TargetDir)
	if err != nil {
		respondError(w, http.StatusInternalServerError, err.Error())
		return
	}
	room.PruneStaleShifts(rd)
	respondJSON(w, http.StatusOK, rd)
}

type ClockInRequest struct {
	AgentID string   `json:"agent_id"`
	Role    string   `json:"role"`
	Task    string   `json:"task"`
	Files   []string `json:"files"`
	Force   bool     `json:"force"`
}

func (s *Server) handleClockIn(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		respondError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}
	var req ClockInRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "Invalid JSON payload")
		return
	}
	shift, token, conflicts, err := room.ClockIn(s.TargetDir, req.AgentID, req.Role, req.Task, req.Files, req.Force)
	if err != nil {
		respondJSON(w, http.StatusConflict, map[string]any{
			"error":     err.Error(),
			"conflicts": conflicts,
		})
		return
	}
	respondJSON(w, http.StatusOK, map[string]any{
		"shift":         shift,
		"session_token": token,
	})
}

type ClockOutRequest struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
	Summary   string `json:"summary"`
}

func (s *Server) handleClockOut(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		respondError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}
	var req ClockOutRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "Invalid JSON payload")
		return
	}
	entry, err := room.ClockOut(s.TargetDir, req.SessionID, req.AgentID, req.Summary)
	if err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusOK, entry)
}

type HeartbeatRequest struct {
	SessionID string `json:"session_id"`
	AgentID   string `json:"agent_id"`
}

func (s *Server) handleHeartbeat(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		respondError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}
	var req HeartbeatRequest
	_ = json.NewDecoder(r.Body).Decode(&req)
	shift, err := room.Heartbeat(s.TargetDir, req.SessionID, req.AgentID)
	if err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusOK, shift)
}

func (s *Server) handleInbox(w http.ResponseWriter, r *http.Request) {
	agentID := strings.TrimPrefix(r.URL.Path, "/api/v1/inbox/")
	if agentID == "" {
		respondError(w, http.StatusBadRequest, "agent_id path parameter required")
		return
	}
	unreadOnly := r.URL.Query().Get("unread") == "true"
	msgs, err := messaging.ReadInbox(s.TargetDir, agentID, unreadOnly)
	if err != nil {
		respondError(w, http.StatusInternalServerError, err.Error())
		return
	}
	respondJSON(w, http.StatusOK, map[string]any{
		"agent_id": agentID,
		"messages": msgs,
	})
}

type SendMessageRequest struct {
	From string          `json:"from"`
	To   string          `json:"to"`
	Body string          `json:"body"`
	Data json.RawMessage `json:"data,omitempty"`
}

func (s *Server) handleSendMessage(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		respondError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}
	var req SendMessageRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "Invalid JSON payload")
		return
	}
	msg, err := messaging.Send(s.TargetDir, req.From, req.To, req.Body, req.Data)
	if err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusOK, msg)
}

type AckRequest struct {
	AgentID   string `json:"agent_id"`
	MessageID string `json:"message_id"`
}

func (s *Server) handleAckMessage(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		respondError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}
	var req AckRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "Invalid JSON payload")
		return
	}
	if err := messaging.Ack(s.TargetDir, req.AgentID, req.MessageID); err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusOK, map[string]string{"status": "acked"})
}

type RouteRequestPayload struct {
	Task string `json:"task"`
}

func (s *Server) handleRoute(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		respondError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}
	var req RouteRequestPayload
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "Invalid JSON payload")
		return
	}
	dec := routing.RouteTask(req.Task, s.ResourceRoot, s.Registry)
	respondJSON(w, http.StatusOK, dec)
}

func (s *Server) handleBots(w http.ResponseWriter, r *http.Request) {
	bots := s.Registry.ListBots()
	respondJSON(w, http.StatusOK, map[string]any{
		"bots":  bots,
		"total": len(bots),
	})
}

func respondJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func respondError(w http.ResponseWriter, status int, msg string) {
	respondJSON(w, status, map[string]string{"error": msg})
}
