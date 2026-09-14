import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  images: { unoptimized: true },
  experimental: {
    // next dev 的 webpack 编译会另起几个子进程，各占几百 MB。内存吃紧的机器上
    // 它们抢不到内存就被杀，表现为浏览器里的
    // "Jest worker encountered 2 child process exceptions, exceeding retry limit"，
    // 且是已编译路由能用、未编译路由全 500 的"半死不活"状态。
    // 这个开关让 webpack 在 dev 下用更少内存换稍慢的编译。
    // 只影响 dev；生产构建（next build / next start）不受影响。
    webpackMemoryOptimizations: true,
  },
};

export default nextConfig;
