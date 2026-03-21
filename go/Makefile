.PHONY: build test lint fmt generate clean check

build:
	go build -o bin/clara ./cmd/clara
	go build -o bin/clara-cli ./cmd/clara-cli

test:
	go test ./... -v -count=1

lint:
	golangci-lint run ./...

fmt:
	gofmt -s -w .

generate:
	sqlc generate

clean:
	rm -rf bin/

check:
	go vet ./...
	go build ./...
