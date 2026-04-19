module Api
  module V1
    class ObsidianController < ApplicationController
      def show
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/obsidian",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def update
        result = GatewayProxy.forward(
          method: :put,
          path: "/api/v1/obsidian",
          user_id: current_user.canonical_user_id,
          body: proxy_body
        )
        render json: result[:body], status: result[:status]
      end

      def destroy
        result = GatewayProxy.forward(
          method: :delete,
          path: "/api/v1/obsidian",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def test
        result = GatewayProxy.forward(
          method: :post,
          path: "/api/v1/obsidian/test",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      private

      def proxy_body
        params.except(:controller, :action, :id, :format).permit!.to_h
      end
    end
  end
end
