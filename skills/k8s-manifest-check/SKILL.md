---
name: k8s-manifest-check
description: Kubernetes 清单体检、K8s YAML 生产就绪检查、Deployment 安全基线、资源 requests/limits 缺失、探针缺失、镜像 latest、特权容器、hostNetwork、hostPath、明文密码写进 env、selector 与 labels 不匹配、废弃 apiVersion、CronJob 并发策略、NodePort 暴露、Ingress 无 TLS。当用户说「帮我检查这些 K8s YAML 有没有问题」「上线前看看 Deployment 配置」「这个 Pod 为什么不安全」「资源限制有没有配」「K8s 清单 lint」时使用。附脚本 scripts/k8s_check.py：内置最小 YAML 解析（不依赖 PyYAML 与 kubectl），覆盖 Deployment/StatefulSet/DaemonSet/Job/CronJob/Pod/Service/Ingress，17 条规则分 high/warn/info 并附改法；识别 Helm 模板提示先渲染；支持目录递归、--json、--strict。
author: Captain
version: 0.1.1
display_name: "K8s 配置检查"
display_name_en: "Kubernetes Manifest Check"
description_zh: "不装任何依赖就能给 Kubernetes YAML 做生产就绪检查：安全基线（特权、root、hostNetwork、hostPath、明文密钥）、可靠性（资源限制、探针、副本、selector 匹配）、废弃 API、CronJob 与暴露面；分级输出附改法，可作 CI 门禁。"
description_en: "Production-readiness checks for Kubernetes YAML with zero dependencies: security baseline (privileged, root, hostNetwork, hostPath, plaintext secrets), reliability (resources, probes, replicas, selector match), deprecated APIs, CronJob and exposure; graded output with fixes, CI-gate ready."
examples_zh:
  - "检查 k8s/ 目录下的清单有哪些生产就绪问题"
  - "这个 Deployment 的安全配置够不够"
  - "把 K8s 清单检查加进 CI，有 warn 就失败"
examples_en:
  - "Check the manifests under k8s/ for production-readiness issues"
  - "Is this Deployment's security configuration sufficient?"
  - "Add the manifest check to CI and fail on warnings"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "☸️" } }
---

# K8s 清单体检

给 Kubernetes YAML 做一次生产就绪检查：安全、可靠性、废弃 API、暴露面。脚本自带最小 YAML 解析器，不需要 PyYAML、kubectl 或集群访问。

## 用法

```bash
python3 scripts/k8s_check.py k8s/                       # 目录递归 *.yaml / *.yml
python3 scripts/k8s_check.py deploy/api.yaml deploy/cron.yaml
python3 scripts/k8s_check.py k8s/ --json
python3 scripts/k8s_check.py k8s/ --strict              # 有 high/warn 退出码 1
helm template myapp charts/myapp > /tmp/rendered.yaml && python3 scripts/k8s_check.py /tmp/rendered.yaml
```

## 流程

1. 跑脚本；**high** 必须处理：特权容器、hostNetwork/hostPID/hostIPC、selector 与 labels 不匹配、明文密钥写进 env。
2. **warn** 上线前处理：镜像未固定版本、缺 requests/limits、缺 readinessProbe、未声明 runAsNonRoot、hostPath、latest + IfNotPresent、废弃 apiVersion。
3. **info** 按团队基线取舍：livenessProbe、allowPrivilegeEscalation、只读根文件系统、drop ALL、单副本、namespace、default SA token、NodePort/LoadBalancer、Ingress TLS、CronJob 策略。
4. 加进 CI：对渲染后的清单跑 `--strict`；例外用注释说明并在团队基线文档里登记。

## 规则一览

| 级别 | 规则 | 检查点 |
|---|---|---|
| high | K004 / K005 / K009 / K010 | privileged；hostNetwork/hostPID/hostIPC；selector 与 labels 不匹配；SECRET/PASSWORD/TOKEN 类 env 用明文 value |
| warn | K001 / K002 / K003 | 镜像无标签或 latest；缺 requests(cpu/memory) 或 limits.memory；缺 readinessProbe |
| warn | K004 / K006 / K008 / K018 | 未声明 runAsNonRoot；hostPath 卷；latest + IfNotPresent；废弃 apiVersion |
| info | K003 / K004 / K007 / K011 / K012 / K013 / K017 / K019 | 缺 livenessProbe；提权/只读根/capabilities；单副本；无 namespace；NodePort/LoadBalancer；CronJob 策略；Ingress 无 TLS；default SA 自动挂载 token |
| info | K000 | 文件内容含 `{{ }}`，判定为 Helm 模板，跳过检查并提示先渲染 |

## 边界

- 最小 YAML 解析支持常见块结构与单行 flow 集合（`{cpu: 100m}`、`["ALL"]`），不支持锚点合并 `<<: *x`、多行 flow 集合与复杂标量；这类文件建议先用 `kubectl apply --dry-run=client -o yaml` 或 `yq` 规范化。
- Helm/Kustomize 模板先渲染再检查；检测到 `{{ }}` 会提示。
- 只做静态检查，不校验字段是否存在于该 API 版本的 schema（用 kubeconform 补充）。
