declare module "@rails/actioncable" {
  interface Subscription {
    unsubscribe(): void;
    perform(action: string, data?: Record<string, unknown>): void;
    send(data: Record<string, unknown>): void;
  }

  interface Subscriptions {
    create(
      channel: string | { channel: string; [key: string]: unknown },
      mixin?: {
        connected?: () => void;
        disconnected?: () => void;
        received?: (data: unknown) => void;
        [key: string]: unknown;
      }
    ): Subscription;
  }

  interface Consumer {
    subscriptions: Subscriptions;
    disconnect(): void;
  }

  export function createConsumer(url?: string): Consumer;
}
