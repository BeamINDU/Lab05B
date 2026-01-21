/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.watchOptions = {
        poll: 1000, // Check for changes every second
        aggregateTimeout: 300, // Delay before rebuilding
      };
    }
    return config;
  },
  env: {
    CHOKIDAR_USEPOLLING: 'true',
    WATCHPACK_POLLING: 'true',
  },
  redirects: async () => {
    return [
      {
        source: '/',
        destination: '/home',
        permanent: true,
      }
    ]
  },
  transpilePackages: ['@react-pdf/renderer'],
};

export default nextConfig;