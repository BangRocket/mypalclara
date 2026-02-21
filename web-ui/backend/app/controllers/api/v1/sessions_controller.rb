module Api
  module V1
    class SessionsController < ApplicationController
      def index
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/sessions",
          user_id: current_user.canonical_user_id,
          params: request.query_parameters
        )
        render json: result[:body], status: result[:status]
      end

      def show
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/sessions/#{params[:id]}",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def update
        result = GatewayProxy.forward(
          method: :put,
          path: "/api/v1/sessions/#{params[:id]}",
          user_id: current_user.canonical_user_id,
          body: proxy_body
        )
        render json: result[:body], status: result[:status]
      end

      def destroy
        result = GatewayProxy.forward(
          method: :delete,
          path: "/api/v1/sessions/#{params[:id]}",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def archive
        result = GatewayProxy.forward(
          method: :patch,
          path: "/api/v1/sessions/#{params[:id]}/archive",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def unarchive
        result = GatewayProxy.forward(
          method: :patch,
          path: "/api/v1/sessions/#{params[:id]}/unarchive",
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
