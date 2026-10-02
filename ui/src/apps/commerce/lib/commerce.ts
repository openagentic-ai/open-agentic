const tokenKey = 'openagentic-commerce-token'
const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export function accessToken() { return sessionStorage.getItem(tokenKey) }
export function setAccessToken(token: string | null) {
  if (token) sessionStorage.setItem(tokenKey, token)
  else sessionStorage.removeItem(tokenKey)
}

export async function commerceRequest<T>(path: string, options: RequestInit = {}, auth = true): Promise<T> {
  const token = auth ? accessToken() : null
  const response = await fetch(`${base}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  const body = await response.json()
  if (!response.ok) {
    if (response.status === 401 && auth) {
      setAccessToken(null)
      window.dispatchEvent(new Event('commerce-auth-expired'))
    }
    const messages: Record<string, string> = {
      'Invalid email or password': '邮箱或密码不正确',
      'Email already registered': '这个邮箱已经注册，请直接登录',
      'Quote not found': '报价不存在或不属于当前账号',
      'Quote expired; request a new quote': '报价已过期，请重新获取报价',
      'Service changed; request a new quote': '服务已变更，请重新获取报价后确认',
      'Agent permission denied': 'Agent 没有这项权限',
      'Request a refund before cancelling a paid order': '请先申请退款，退款成功后再取消预约',
      'Payment provider not enabled': '当前未启用支付，请使用本地演练入口',
      'Merchant must accept the order before payment': '请等待商家接单，再演练支付',
      'Not authenticated': '请先登录', 'Invalid token': '登录已过期，请重新登录',
      'Merchant not found': '店铺不存在或你没有管理权限',
      'Storefront not found': '店铺不存在', 'Account is inactive': '账号已停用',
      'Please choose a future time': '请选择未来的服务时间',
      'Published service not found': '服务已下架或不存在，请重新选择',
      'Service price changed; review it before confirming': '服务价格已更新，请返回店铺确认新价格',
      'Request ID already used for another booking': '这次提交已有预约记录，请先到“我的预约”确认结果',
      'Order not found': '订单不存在或你没有查看权限',
      'Invalid order status transition': '订单状态已变化，请刷新后再操作',
      'Order cannot be cancelled in its current status': '当前订单状态无法取消',
    }
    const detail = typeof body.detail === 'string' ? body.detail : '请检查填写内容后重试'
    throw new Error(messages[detail] || detail)
  }
  return body as T
}

export interface MerchantInput {
  name: string; region: string; description: string; contact_name: string; contact_phone: string
}
export interface Merchant extends MerchantInput { id: string }
export interface ServiceInput {
  name: string; description: string; price_fen: number; duration_minutes: number
  availability_note: string; is_published: boolean
}
export interface Service extends ServiceInput { id: string; merchant_id: string }
export type PublishedService = Omit<Service, 'is_published'>
export interface Storefront {
  merchant: Pick<Merchant, 'id' | 'name' | 'region' | 'description'>
  services: PublishedService[]
}
export function serviceInput(service: Service): ServiceInput {
  const { name, description, price_fen, duration_minutes, availability_note, is_published } = service
  return { name, description, price_fen, duration_minutes, availability_note, is_published }
}
export function money(fen: number) {
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(fen / 100)
}

export interface Booking {
  id: string; merchant_id: string; service_id: string; service_name: string
  price_fen: number; duration_minutes: number; preferred_at: string
  customer_name: string; customer_phone: string; note: string
  status: 'pending' | 'accepted' | 'completed' | 'declined' | 'cancelled'
}
export const bookingLabels: Record<Booking['status'], string> = {
  pending: '待商家确认', accepted: '已接单', completed: '已完成', declined: '商家已拒绝', cancelled: '已取消',
}
export function bookingTime(value: string) {
  // SQLite stores UTC timestamps without the zone marker; PostgreSQL returns offsets.
  const utc = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`
  return new Date(utc).toLocaleString('zh-CN', { hour12: false })
}
