Rails.application.routes.draw do
  # Auth stays at top level
  get "auth/login", to: "auth#login"
  get "auth/callback", to: "auth#callback"
  delete "auth/logout", to: "auth#logout"

  namespace :api do
    namespace :v1 do
      resources :games, only: [:create, :show] do
        member do
          post :move
          post :ai_move
        end
      end
      get "lobby", to: "lobby#index"
      resources :history, only: [:index, :show]
    end
  end

  # Health check
  get "up" => "rails/health#show", as: :rails_health_check
end
