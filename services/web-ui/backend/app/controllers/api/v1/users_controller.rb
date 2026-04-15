module Api
  module V1
    class UsersController < ApplicationController
      def me
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/users/me",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def update_me
        result = GatewayProxy.forward(
          method: :put,
          path: "/api/v1/users/me",
          user_id: current_user.canonical_user_id,
          body: proxy_body
        )
        render json: result[:body], status: result[:status]
      end

      def links
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/users/me/links",
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
