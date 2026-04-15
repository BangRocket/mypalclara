class ChatChannel < ApplicationCable::Channel
  def subscribed
    stream_for current_user
  end

  def receive(data)
    request_id = SecureRandom.uuid
    user = current_user

    GatewayWsClient.instance.register_callback(request_id) do |event|
      ChatChannel.broadcast_to(user, event)

      # Unregister on terminal events
      if %w[response_end error cancelled].include?(event["type"])
        GatewayWsClient.instance.unregister_callback(request_id)
      end
    end

    GatewayWsClient.instance.send_message(
      request_id: request_id,
      content: data["content"],
      user_id: "web-#{current_user.canonical_user_id}",
      display_name: current_user.display_name || "User",
      tier: data["tier"]
    )
  end

  def unsubscribed
    # Cleanup handled by callback unregistration on terminal events
  end
end
