require "websocket-client-simple"
require "json"
require "singleton"

class GatewayWsClient
  include Singleton

  GATEWAY_URL = ENV.fetch("CLARA_GATEWAY_URL", "ws://127.0.0.1:18789")

  def initialize
    @callbacks = {}
    @mutex = Mutex.new
    @ws = nil
    @connected = false
  end

  def ensure_connected
    return if @connected && @ws
    connect
  end

  def connected?
    @connected
  end

  def send_message(request_id:, content:, user_id:, display_name:, tier: nil)
    ensure_connected

    msg = {
      type: "message",
      request_id: request_id,
      user: { id: user_id, platform_id: user_id, name: display_name, display_name: display_name },
      channel: { id: "web-chat", type: "dm", name: "Web Chat" },
      content: content,
      platform: "web",
      capabilities: ["streaming", "tool_display"]
    }
    msg[:tier_override] = tier if tier
    @ws&.send(msg.to_json)
  end

  def register_callback(request_id, &block)
    @mutex.synchronize { @callbacks[request_id] = block }
  end

  def unregister_callback(request_id)
    @mutex.synchronize { @callbacks.delete(request_id) }
  end

  private

  def connect
    @ws = WebSocket::Client::Simple.connect(GATEWAY_URL)
    client = self

    @ws.on :open do
      # Send registration message
      register_msg = {
        type: "register",
        platform: "web",
        capabilities: ["streaming", "tool_display"]
      }
      send(register_msg.to_json)
      client.instance_variable_set(:@connected, true)
      Rails.logger.info("GatewayWsClient: Connected to gateway")
    end

    @ws.on :message do |msg|
      begin
        data = JSON.parse(msg.data)
        rid = data["request_id"]
        if rid
          client.instance_variable_get(:@mutex).synchronize do
            cb = client.instance_variable_get(:@callbacks)[rid]
            cb&.call(data)
          end
        end
      rescue JSON::ParserError => e
        Rails.logger.warn("GatewayWsClient: Failed to parse message: #{e.message}")
      end
    end

    @ws.on :close do
      client.instance_variable_set(:@connected, false)
      Rails.logger.warn("GatewayWsClient: Disconnected from gateway")
      # Auto-reconnect with exponential backoff
      Thread.new do
        delay = 5
        max_delay = 300
        max_retries = 20
        retries = 0
        loop do
          break if retries >= max_retries
          sleep delay
          begin
            client.send(:connect)
            break
          rescue => e
            retries += 1
            Rails.logger.warn("GatewayWsClient: Reconnect attempt #{retries} failed: #{e.message}")
            delay = [delay * 2, max_delay].min
          end
        end
        Rails.logger.error("GatewayWsClient: Gave up reconnecting after #{max_retries} attempts") if retries >= max_retries
      end
    end

    @ws.on :error do |e|
      Rails.logger.error("GatewayWsClient: WebSocket error: #{e.message}")
    end
  end
end
