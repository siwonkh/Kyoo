package api

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/golang-jwt/jwt/v5"
	"github.com/labstack/echo/v5"
	"github.com/zoriya/kyoo/transcoder/src"
)

func TestPlaybackRequiresVerifiedUser(t *testing.T) {
	original := src.Settings.JwksUrl
	src.Settings.JwksUrl = "http://auth.example/.well-known/jwks.json"
	t.Cleanup(func() { src.Settings.JwksUrl = original })
	for _, tt := range []struct {
		name string
		verified any
		permissions []any
		allowed bool
	}{
		{name: "unverified", verified: false, permissions: []any{"core.play"}},
		{name: "missing verification", permissions: []any{"core.play"}},
		{name: "verified without play permission", verified: true},
		{name: "verified", verified: true, permissions: []any{"core.play"}, allowed: true},
	} {
		t.Run(tt.name, func(t *testing.T) {
			e := echo.New()
			c := e.NewContext(httptest.NewRequest(http.MethodGet, "/video/example", nil), httptest.NewRecorder())
			c.Set("user", jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
				"verified": tt.verified,
				"permissions": tt.permissions,
			}))
			called := false
			err := RequirePermission("core.play")(func(*echo.Context) error {
				called = true
				return nil
			})(c)
			if tt.allowed {
				if err != nil || !called { t.Fatalf("verified user blocked: err=%v, called=%v", err, called) }
				return
			}
			if called { t.Fatal("unauthorized user reached playback handler") }
			if httpErr, ok := err.(*echo.HTTPError); !ok || httpErr.Code != http.StatusForbidden {
				t.Fatalf("expected HTTP 403, got %v", err)
			}
		})
	}
}

