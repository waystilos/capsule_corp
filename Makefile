.PHONY: all build test check verify security attack grill doctor hook install serve sync clean

BINARY := bin/capsule-go

all: build

build:
	go build -v -o $(BINARY) ./cmd/capsule

test:
	go test -v ./...

check: build
	./bin/capsule check .

verify: build
	./bin/capsule verify .

security: build
	./bin/capsule security .

attack: build
	./bin/capsule attack .

grill: build
	./bin/capsule grill .

doctor: build
	./bin/capsule doctor

hook: build
	./bin/capsule hook install

install: build
	./bin/capsule install

serve: build
	./$(BINARY) serve --port 8080

sync: build
	./bin/capsule sync --force

clean:
	rm -f $(BINARY) bin/capsule-go.exe
	go clean -testcache
