Rails.application.routes.draw do
  get "auth/login", to: "auth#login"
  get "auth/callback", to: "auth#callback"
  delete "auth/logout", to: "auth#logout"

  resources :games, only: [:create, :show] do
    member do
      post :move
      post :ai_move
    end
  end

  resources :history, only: [:index, :show]

  # Health check for load balancers and uptime monitors
  get "up" => "rails/health#show", as: :rails_health_check

  # Root route - Game lobby
  root "lobby#index"
end
