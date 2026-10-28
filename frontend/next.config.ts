import path from "path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    // Pins the project root to this folder explicitly. Without this,
    // Turbopack infers the root from the nearest lockfile and can walk up
    // past it (e.g. into a parent directory also containing a
    // package-lock.json), which triggers a spurious "ignored lockfile
    // because it would include your home directory" warning on machines
    // whose user profile folder happens to sit above this project.
    root: path.join(__dirname),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
