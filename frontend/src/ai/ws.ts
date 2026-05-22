type ProgressPayload = {
  status: string;
  percentage: number;
  message: string;
};

type WSEventMap = {
  progress: (payload: ProgressPayload) => void;
  token: (token: string) => void;
  error: (message: string) => void;
  complete: (payload: any) => void;
  connected: () => void;
};

export class JobWebSocketClient {
  private ws: WebSocket | null = null;
  private listeners: Partial<WSEventMap> = {};
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor(private taskId: string, private baseUrl: string = "ws://localhost:8000/api/v1/ws") {}

  public connect(): void {
    const url = `${this.baseUrl}/${this.taskId}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      console.log(`WebSocket connected to task channel: ${this.taskId}`);
    };

    this.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const eventName = payload.event as keyof WSEventMap;
        
        if (eventName === "progress" && this.listeners.progress) {
          this.listeners.progress(payload.payload as ProgressPayload);
        } else if (eventName === "token" && this.listeners.token) {
          this.listeners.token(payload.payload.token as string);
        } else if (eventName === "error" && this.listeners.error) {
          this.listeners.error(payload.payload.message as string);
        } else if (eventName === "complete" && this.listeners.complete) {
          this.listeners.complete(payload.payload);
        } else if (eventName === "connected" && this.listeners.connected) {
          this.listeners.connected();
        }
      } catch (err) {
        console.error("Failed to parse WebSocket message:", err);
      }
    };

    this.ws.onclose = (event) => {
      console.log(`WebSocket closed: ${event.reason}`);
      if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        const timeout = Math.pow(2, this.reconnectAttempts) * 1000;
        console.log(`Attempting reconnection in ${timeout}ms...`);
        setTimeout(() => this.connect(), timeout);
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket connection error:", error);
    };
  }

  public on<K extends keyof WSEventMap>(event: K, callback: WSEventMap[K]): this {
    this.listeners[event] = callback as any;
    return this;
  }

  public disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, "Component unmounted");
      this.ws = null;
    }
  }
}
