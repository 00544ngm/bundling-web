"use client";

import { RotateCcw } from "lucide-react";

interface JobErrorProps {
  errorCode: string;
  errorMessage: string;
  onRetry?: () => void;
  isRetrying?: boolean;
}

function explainProviderFailure(errorCode: string, errorMessage: string) {
  const normalized = `${errorCode} ${errorMessage}`.toLowerCase();
  const stableProviderErrors: Record<string, { title: string; action: string }> = {
    provider_auth_failed: {
      title: "API Key 无效",
      action: "请进入 API 设置重新输入 API Key，并重新验证所选模型。",
    },
    provider_permission_denied: {
      title: "没有所选模型的访问权限",
      action: "请确认当前 API Key 已开通该模型，或改选已通过验证的模型。",
    },
    provider_model_invalid: {
      title: "模型不存在或当前不可用",
      action: "请进入 API 设置核对模型名称，并重新验证模型。",
    },
    provider_protocol_mismatch: {
      title: "接口协议不匹配",
      action: "OpenAI 兼容服务需支持 /v1/chat/completions 或 /v1/responses；Anthropic 兼容服务需支持 /v1/messages。请核对服务地址和所选协议后重新验证模型。",
    },
    provider_structured_output_unsupported: {
      title: "结构化输出模式不受支持",
      action: "请进入 API 设置重新验证模型，软件会依次检测该服务实际支持的结构化输出模式。",
    },
    provider_request_too_large: {
      title: "请求内容超过服务限制",
      action: "当前第三方服务无法接收本次完整报告请求，请联系服务商提高请求限制。",
    },
    provider_quota_exhausted: {
      title: "供应商账户额度已用尽",
      action: "这不是限流，等待不会有改善。请为该供应商账户充值后重试。",
    },
    provider_rate_limited: {
      title: "模型服务正在限流",
      action: "请稍后重试；开启模型轮换时，系统会按已验证顺序尝试下一个模型。",
    },
    provider_upstream_unavailable: {
      title: "上游模型服务暂时不可用",
      action: "请稍后重试；开启模型轮换时，系统会按已验证顺序继续尝试。",
    },
    provider_model_task_timeout: {
      title: "模型报告生成超时",
      action: "请重新提交任务，或开启模型轮换使用其他已验证模型。",
    },
    provider_connection_failed: {
      title: "无法连接模型服务",
      action: "请检查服务地址、员工电脑网络和代理设置，然后重新验证模型。",
    },
    provider_empty_response: {
      title: "模型返回了空内容",
      action: "请重新验证该模型；开启模型轮换时，系统会尝试下一个已验证模型。",
    },
    model_invalid_json: {
      title: "模型报告格式不完整",
      action: "该模型未完成结构化报告，请重新提交或启用模型轮换。",
    },
    walmart_navigation_timeout: {
      title: "Walmart 页面加载超时",
      action: "请检查员工电脑的网络、代理或安全软件后重新提交任务。",
    },
    walmart_network_failed: {
      title: "无法连接 Walmart",
      action: "请检查员工电脑的网络、代理和安全软件设置后重试。",
    },
    walmart_captcha_timeout: {
      title: "Walmart 人工验证未完成",
      action: "请重新提交任务，并在自动打开的 Walmart 窗口中完成验证。验证成功前不会调用模型，也不会消耗 Token。",
    },
  };
  const stableCode = errorCode.trim().toLowerCase();
  if (stableProviderErrors[stableCode]) return stableProviderErrors[stableCode];
  if (normalized.includes("walmart_captcha_timeout")) {
    return {
      title: "Walmart 人工验证未完成",
      action: "请重新提交任务，并在自动打开的 Walmart 窗口中完成验证。验证成功前不会调用模型，也不会消耗 Token。",
    };
  }
  if (normalized.includes("browser_target_closed") || normalized.includes("targetclosed")) {
    return {
      title: "商品浏览器已意外关闭",
      action: "软件会在模型调用前自动重启浏览器并重试一次；如仍失败，请运行环境检查。",
    };
  }
  if (normalized.includes("provider_config_decrypt_failed")) {
    return {
      title: "当前 Windows 用户无法读取已保存的 API Key",
      action: "请在这台员工电脑的当前 Windows 用户下进入 API 设置，重新输入 API Key、验证模型并保存。",
    };
  }
  if (normalized.includes("not supported by any configured account in this group")) {
    return {
      title: "当前账户分组无法路由到所选模型",
      action: "前往 API 设置重新验证该模型；验证通过后再重新提交任务。",
    };
  }
  if (normalized.includes("provider_model_not_verified")) {
    return {
      title: "所选模型尚未通过真实任务验证",
      action: "软件会在连接配置变化或任务失败时自动验证；也可前往 API 设置手动重新验证。",
    };
  }
  if (normalized.includes("502") || normalized.includes("503")) {
    return {
      title: "上游模型服务暂时不可用",
      action: "稍后重新验证同一模型；系统不会自动切换到其他付费模型。",
    };
  }
  return { title: "任务执行失败", action: "请根据技术详情检查配置后重试。" };
}

export default function JobError({
  errorCode,
  errorMessage,
  onRetry,
  isRetrying,
}: JobErrorProps) {
  const explanation = explainProviderFailure(errorCode, errorMessage);
  const normalized = `${errorCode} ${errorMessage}`.toLowerCase();
  const stableWalmartError = new Set([
    "walmart_navigation_timeout",
    "walmart_network_failed",
    "walmart_captcha_timeout",
  ]).has(errorCode.trim().toLowerCase());
  const technicalMessage = stableWalmartError ? "" : errorMessage;
  const browserFailure = normalized.includes("browser_target_closed") || normalized.includes("targetclosed");
  return (
    <div className="space-y-3 rounded-md border border-destructive/30 bg-destructive/5 p-4">
      <div className="space-y-1">
        <p className="text-sm font-medium text-destructive">{explanation.title}</p>
        <p className="text-sm text-muted-foreground">{explanation.action}</p>
        {technicalMessage && <p className="text-xs text-muted-foreground">{technicalMessage}</p>}
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer">技术详情</summary>
          <p className="mt-1 break-words">错误代码：{errorCode}</p>
        </details>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={isRetrying}
          className="inline-flex items-center gap-2 rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          <RotateCcw className="h-4 w-4" />
          {isRetrying ? "重新提交中..." : browserFailure ? "自动修复后重试" : "重新提交"}
        </button>
      )}
    </div>
  );
}
