package vector

import (
	"context"
	"fmt"
	"net"
	"os"
	"strconv"

	"github.com/qdrant/go-client/qdrant"
)

// QdrantStore implements VectorStore using the Qdrant gRPC client.
type QdrantStore struct {
	client         *qdrant.Client
	collectionName string
}

// NewQdrantStore creates a new QdrantStore connected to the Qdrant instance
// at the given URL using the provided API key and collection name.
//
// The url should be a host:port string for gRPC (default: localhost:6334).
// If url or apiKey are empty, they are read from QDRANT_URL and QDRANT_API_KEY
// environment variables respectively.
func NewQdrantStore(url string, apiKey string, collectionName string) (*QdrantStore, error) {
	if url == "" {
		url = os.Getenv("QDRANT_URL")
	}
	if url == "" {
		url = "localhost:6334"
	}
	if apiKey == "" {
		apiKey = os.Getenv("QDRANT_API_KEY")
	}

	host, portStr, err := net.SplitHostPort(url)
	if err != nil {
		return nil, fmt.Errorf("invalid qdrant URL %q: %w", url, err)
	}
	port, err := strconv.Atoi(portStr)
	if err != nil {
		return nil, fmt.Errorf("invalid port in qdrant URL %q: %w", url, err)
	}

	client, err := qdrant.NewClient(&qdrant.Config{
		Host:   host,
		Port:   port,
		APIKey: apiKey,
		UseTLS: apiKey != "",
	})
	if err != nil {
		return nil, fmt.Errorf("creating qdrant client: %w", err)
	}

	return &QdrantStore{
		client:         client,
		collectionName: collectionName,
	}, nil
}

// newQdrantStoreWithClient creates a QdrantStore with an injected client.
// Used for testing.
func newQdrantStoreWithClient(client *qdrant.Client, collectionName string) *QdrantStore {
	return &QdrantStore{
		client:         client,
		collectionName: collectionName,
	}
}

// Close closes the underlying Qdrant client connection.
func (q *QdrantStore) Close() error {
	return q.client.Close()
}

// CreateCollection creates a new Qdrant collection with the given name and
// vector size, using cosine distance.
func (q *QdrantStore) CreateCollection(ctx context.Context, name string, vectorSize int) error {
	return q.client.CreateCollection(ctx, &qdrant.CreateCollection{
		CollectionName: name,
		VectorsConfig: qdrant.NewVectorsConfig(&qdrant.VectorParams{
			Size:     uint64(vectorSize),
			Distance: qdrant.Distance_Cosine,
		}),
	})
}

// Upsert inserts or updates a point with the given ID, vector, and payload.
func (q *QdrantStore) Upsert(ctx context.Context, id string, vector []float32, payload map[string]any) error {
	pointID := qdrant.NewIDUUID(id)
	qdrantPayload := qdrant.NewValueMap(payload)

	_, err := q.client.Upsert(ctx, &qdrant.UpsertPoints{
		CollectionName: q.collectionName,
		Points: []*qdrant.PointStruct{
			{
				Id:      pointID,
				Vectors: qdrant.NewVectorsDense(vector),
				Payload: qdrantPayload,
			},
		},
	})
	return err
}

// Search performs a similarity search against the collection, returning up to
// limit results filtered by the optional filter. Results are sorted by score
// descending (Qdrant default).
func (q *QdrantStore) Search(ctx context.Context, vector []float32, limit int, filter *Filter) ([]SearchResult, error) {
	request := &qdrant.QueryPoints{
		CollectionName: q.collectionName,
		Query:          qdrant.NewQueryDense(vector),
		Limit:          qdrant.PtrOf(uint64(limit)),
		WithPayload:    qdrant.NewWithPayload(true),
		Filter:         buildQdrantFilter(filter),
	}

	scored, err := q.client.Query(ctx, request)
	if err != nil {
		return nil, err
	}

	results := make([]SearchResult, 0, len(scored))
	for _, sp := range scored {
		results = append(results, scoredPointToResult(sp))
	}
	return results, nil
}

// Get retrieves a single point by its UUID string ID.
func (q *QdrantStore) Get(ctx context.Context, id string) (*SearchResult, error) {
	pointID := qdrant.NewIDUUID(id)
	points, err := q.client.Get(ctx, &qdrant.GetPoints{
		CollectionName: q.collectionName,
		Ids:            []*qdrant.PointId{pointID},
		WithPayload:    qdrant.NewWithPayload(true),
		WithVectors:    qdrant.NewWithVectors(true),
	})
	if err != nil {
		return nil, err
	}
	if len(points) == 0 {
		return nil, fmt.Errorf("point %q not found", id)
	}

	result := retrievedPointToResult(points[0])
	return &result, nil
}

// Delete removes a point by its UUID string ID.
func (q *QdrantStore) Delete(ctx context.Context, id string) error {
	pointID := qdrant.NewIDUUID(id)
	_, err := q.client.Delete(ctx, &qdrant.DeletePoints{
		CollectionName: q.collectionName,
		Points: &qdrant.PointsSelector{
			PointsSelectorOneOf: &qdrant.PointsSelector_Points{
				Points: &qdrant.PointsIdsList{
					Ids: []*qdrant.PointId{pointID},
				},
			},
		},
	})
	return err
}

// Update replaces the vector and payload for an existing point.
// Implemented as an upsert since Qdrant upsert is idempotent.
func (q *QdrantStore) Update(ctx context.Context, id string, vector []float32, payload map[string]any) error {
	return q.Upsert(ctx, id, vector, payload)
}

// List returns points matching the filter, up to limit, using scroll.
func (q *QdrantStore) List(ctx context.Context, filter *Filter, limit int) ([]SearchResult, error) {
	points, err := q.client.Scroll(ctx, &qdrant.ScrollPoints{
		CollectionName: q.collectionName,
		Filter:         buildQdrantFilter(filter),
		Limit:          qdrant.PtrOf(uint32(limit)),
		WithPayload:    qdrant.NewWithPayload(true),
		WithVectors:    qdrant.NewWithVectors(true),
	})
	if err != nil {
		return nil, err
	}

	results := make([]SearchResult, 0, len(points))
	for _, p := range points {
		results = append(results, retrievedPointToResult(p))
	}
	return results, nil
}

// buildQdrantFilter converts a Filter into a Qdrant filter with Must conditions.
// Returns nil if no filter conditions are present.
func buildQdrantFilter(f *Filter) *qdrant.Filter {
	if f == nil {
		return nil
	}

	var conditions []*qdrant.Condition

	if f.UserID != "" {
		conditions = append(conditions, qdrant.NewMatch("user_id", f.UserID))
	}
	if f.AgentID != "" {
		conditions = append(conditions, qdrant.NewMatch("agent_id", f.AgentID))
	}
	for key, val := range f.Filters {
		switch v := val.(type) {
		case string:
			conditions = append(conditions, qdrant.NewMatch(key, v))
		case int64:
			conditions = append(conditions, qdrant.NewMatchInt(key, v))
		case int:
			conditions = append(conditions, qdrant.NewMatchInt(key, int64(v)))
		case bool:
			conditions = append(conditions, qdrant.NewMatchBool(key, v))
		}
	}

	if len(conditions) == 0 {
		return nil
	}

	return &qdrant.Filter{
		Must: conditions,
	}
}

// scoredPointToResult converts a Qdrant ScoredPoint to a SearchResult.
func scoredPointToResult(sp *qdrant.ScoredPoint) SearchResult {
	result := SearchResult{
		ID:      extractPointID(sp.GetId()),
		Score:   sp.GetScore(),
		Payload: extractPayload(sp.GetPayload()),
	}
	if v := sp.GetVectors(); v != nil {
		if dense := v.GetVector(); dense != nil {
			result.Vector = dense.GetData()
		}
	}
	return result
}

// retrievedPointToResult converts a Qdrant RetrievedPoint to a SearchResult.
func retrievedPointToResult(rp *qdrant.RetrievedPoint) SearchResult {
	result := SearchResult{
		ID:      extractPointID(rp.GetId()),
		Payload: extractPayload(rp.GetPayload()),
	}
	if v := rp.GetVectors(); v != nil {
		if dense := v.GetVector(); dense != nil {
			result.Vector = dense.GetData()
		}
	}
	return result
}

// extractPointID converts a Qdrant PointId to a string.
func extractPointID(id *qdrant.PointId) string {
	if id == nil {
		return ""
	}
	switch v := id.PointIdOptions.(type) {
	case *qdrant.PointId_Uuid:
		return v.Uuid
	case *qdrant.PointId_Num:
		return strconv.FormatUint(v.Num, 10)
	default:
		return ""
	}
}

// extractPayload converts a Qdrant payload map to a generic Go map.
func extractPayload(payload map[string]*qdrant.Value) map[string]any {
	if payload == nil {
		return nil
	}
	result := make(map[string]any, len(payload))
	for k, v := range payload {
		result[k] = extractValue(v)
	}
	return result
}

// extractValue converts a single Qdrant Value to a Go value.
func extractValue(v *qdrant.Value) any {
	if v == nil {
		return nil
	}
	switch kind := v.Kind.(type) {
	case *qdrant.Value_NullValue:
		return nil
	case *qdrant.Value_BoolValue:
		return kind.BoolValue
	case *qdrant.Value_IntegerValue:
		return kind.IntegerValue
	case *qdrant.Value_DoubleValue:
		return kind.DoubleValue
	case *qdrant.Value_StringValue:
		return kind.StringValue
	case *qdrant.Value_StructValue:
		if kind.StructValue == nil {
			return nil
		}
		result := make(map[string]any, len(kind.StructValue.Fields))
		for k, fv := range kind.StructValue.Fields {
			result[k] = extractValue(fv)
		}
		return result
	case *qdrant.Value_ListValue:
		if kind.ListValue == nil {
			return nil
		}
		result := make([]any, len(kind.ListValue.Values))
		for i, lv := range kind.ListValue.Values {
			result[i] = extractValue(lv)
		}
		return result
	default:
		return nil
	}
}
