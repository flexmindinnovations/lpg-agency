import json
from locust import HttpUser, task, between, events
import websocket
import uuid

class LpgApiUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a Locust start before any task is scheduled."""
        self.email = "admin@example.com"
        self.password = "Secret123!"
        self.token = ""
        self.tenant_id = ""
        
        response = self.client.post("/api/v1/auth/login", json={
            "email": self.email,
            "password": self.password
        })
        
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            me_resp = self.client.get("/api/v1/auth/me", headers={
                "Authorization": f"Bearer {self.token}"
            })
            if me_resp.status_code == 200:
                self.tenant_id = me_resp.json().get("tenant_id")
                
        self.ws = None
        if self.token and self.tenant_id:
            ws_url = self.host.replace("http", "ws") + f"/api/v1/ws?token={self.token}"
            try:
                self.ws = websocket.create_connection(ws_url)
                self.ws.send(json.dumps({
                    "subscribe": ["dashboard", f"order:{uuid.uuid4()}"]
                }))
            except Exception as e:
                events.request.fire(
                    request_type="WebSocket",
                    name="connect",
                    response_time=0,
                    response_length=0,
                    exception=e
                )

    def on_stop(self):
        if self.ws:
            self.ws.close()

    @task(3)
    def dashboard_summary(self):
        """Simulate loading the dashboard."""
        if not self.token:
            return
        
        self.client.get("/api/v1/dashboard/summary", headers={
            "Authorization": f"Bearer {self.token}"
        })

    @task(2)
    def recent_orders(self):
        """Simulate polling or fetching orders grid."""
        if not self.token:
            return
            
        self.client.get("/api/v1/orders?skip=0&limit=50", headers={
            "Authorization": f"Bearer {self.token}"
        })
        
    @task(1)
    def ws_keepalive(self):
        """Simulate WebSocket keepalives and listening."""
        if not self.ws:
            return
            
        try:
            self.ws.send(json.dumps({"type": "ping"}))
            self.ws.settimeout(0.5)
            self.ws.recv()
            events.request.fire(
                request_type="WebSocket",
                name="ping",
                response_time=0,
                response_length=0,
                exception=None
            )
        except websocket.WebSocketTimeoutException:
            pass
        except Exception as e:
            events.request.fire(
                request_type="WebSocket",
                name="ping",
                response_time=0,
                response_length=0,
                exception=e
            )
