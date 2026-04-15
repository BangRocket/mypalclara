module Api
  module V1
    class AdminController < ApplicationController
      def users
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/admin/users",
          user_id: current_user.canonical_user_id,
          params: request.query_parameters
        )
        render json: result[:body], status: result[:status]
      end

      def approve
        result = GatewayProxy.forward(
          method: :post,
          path: "/api/v1/admin/users/#{params[:id]}/approve",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def suspend
        result = GatewayProxy.forward(
          method: :post,
          path: "/api/v1/admin/users/#{params[:id]}/suspend",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def pending_count
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/admin/users/pending/count",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end
    end
  end
end
