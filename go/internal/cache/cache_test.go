package cache

import (
	"testing"
	"time"
)

func TestGetSetBasic(t *testing.T) {
	c := New[string, int](time.Minute)
	c.Set("a", 1)
	v, ok := c.Get("a")
	if !ok || v != 1 {
		t.Errorf("expected 1, got %d (ok=%v)", v, ok)
	}
}

func TestGetMiss(t *testing.T) {
	c := New[string, int](time.Minute)
	_, ok := c.Get("missing")
	if ok {
		t.Error("expected miss")
	}
}

func TestTTLExpiry(t *testing.T) {
	c := New[string, int](10 * time.Millisecond)
	c.Set("a", 1)

	v, ok := c.Get("a")
	if !ok || v != 1 {
		t.Error("expected hit before expiry")
	}

	time.Sleep(15 * time.Millisecond)
	_, ok = c.Get("a")
	if ok {
		t.Error("expected miss after expiry")
	}
}

func TestEvict(t *testing.T) {
	c := New[string, int](time.Minute)
	c.Set("a", 1)
	c.Evict("a")
	_, ok := c.Get("a")
	if ok {
		t.Error("expected miss after evict")
	}
}

func TestClear(t *testing.T) {
	c := New[string, int](time.Minute)
	c.Set("a", 1)
	c.Set("b", 2)
	c.Clear()
	_, ok1 := c.Get("a")
	_, ok2 := c.Get("b")
	if ok1 || ok2 {
		t.Error("expected all cleared")
	}
}

func TestEvictExpired(t *testing.T) {
	c := New[string, int](10 * time.Millisecond)
	c.Set("a", 1)
	c.Set("b", 2)
	time.Sleep(15 * time.Millisecond)
	c.Set("c", 3) // added after sleep, still valid

	c.EvictExpired()

	_, okA := c.Get("a")
	_, okB := c.Get("b")
	v, okC := c.Get("c")
	if okA || okB {
		t.Error("a and b should be expired")
	}
	if !okC || v != 3 {
		t.Error("c should still be valid")
	}
}

func TestOverwrite(t *testing.T) {
	c := New[string, int](time.Minute)
	c.Set("a", 1)
	c.Set("a", 2)
	v, ok := c.Get("a")
	if !ok || v != 2 {
		t.Errorf("expected 2, got %d", v)
	}
}
