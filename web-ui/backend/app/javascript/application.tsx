import { createInertiaApp } from "@inertiajs/react"
import { createRoot } from "react-dom/client"
import pages from "./pages"

createInertiaApp({
  resolve: (name: string) => {
    const page = pages[name]
    if (!page) {
      throw new Error(`Page not found: ${name}`)
    }
    return page
  },
  setup({ el, App, props }) {
    createRoot(el).render(<App {...props} />)
  },
})
