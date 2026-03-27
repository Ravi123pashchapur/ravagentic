/**
 * Local mock API + minimal STOMP WebSocket for NEXT_PUBLIC_API_BASE_URL (e.g. http://localhost:8080/api/v1).
 * Covers public customer-gateway routes and authenticated /customer/* + /auth-customer/* paths used by Next.js API routes.
 */

const http = require('http');
const crypto = require('crypto');
const express = require('express');
const cors = require('cors');
const { WebSocketServer } = require('ws');

const PORT = Number(process.env.MOCK_BACKEND_PORT || process.env.PORT || 8080);

// --- Catalog (shared across sessions) -------------------------------------------------
const MOCK_BRANCH_ID = 1;

const MOCK_CATEGORIES = [
  { id: 1, branchId: MOCK_BRANCH_ID, name: 'Skincare', description: 'Mock skincare', imageUrl: 'https://placehold.co/400x200/png?text=Skincare', featured: true },
  { id: 2, branchId: MOCK_BRANCH_ID, name: 'Fragrance', description: 'Mock fragrance', imageUrl: 'https://placehold.co/400x200/png?text=Fragrance', featured: true },
  { id: 3, branchId: MOCK_BRANCH_ID, name: 'Wellness', description: 'Mock wellness', imageUrl: 'https://placehold.co/400x200/png?text=Wellness', featured: false },
];

const productImage = (n) => `https://placehold.co/600x600/png?text=Product+${n}`;

function mockProduct(n) {
  const id = `a000000${n}-0000-4000-8000-00000000000${n}`;
  const basePrice = 15 + n * 5;
  return {
    id,
    branchId: MOCK_BRANCH_ID,
    name: `Mock Product ${n}`,
    description: `Development mock product #${n} with sample description.`,
    active: true,
    available: true,
    featured: n <= 4,
    currency: 'GBP',
    stockMethod: 'QUANTITY',
    taxType: 'VAT',
    taxRate: 20,
    discount: n === 1 ? 10 : 0,
    discountType: n === 1 ? 'PERCENTAGE' : 'NO_DISCOUNT',
    imageUrls: [productImage(n)],
    reviewCount: 3 + n,
    averageRating: 4 + (n % 2) * 0.2,
    attributes: { collection: 'Mock' },
    variations: [{ key: 'Size', options: ['S', 'M', 'L'] }],
    variants: [
      { id: n * 10 + 1, selectedOptions: { Size: 'S' }, price: basePrice, stockQuantity: 20 },
      { id: n * 10 + 2, selectedOptions: { Size: 'M' }, price: basePrice + 2, stockQuantity: 15 },
      { id: n * 10 + 3, selectedOptions: { Size: 'L' }, price: basePrice + 4, stockQuantity: 10 },
    ],
    categoryId: ((n - 1) % MOCK_CATEGORIES.length) + 1,
  };
}

const MOCK_PRODUCTS = [1, 2, 3, 4, 5, 6].map(mockProduct);

function productById(id) {
  return MOCK_PRODUCTS.find((p) => p.id === id) || null;
}

function variantByIds(productId, variantId) {
  const p = productById(productId);
  if (!p) return null;
  const v = p.variants.find((x) => x.id === Number(variantId));
  return v ? { product: p, variant: v } : null;
}

function featuredProductDetails() {
  return MOCK_PRODUCTS.filter((p) => p.featured).map((p) => {
    const v = p.variants[0];
    return {
      id: p.id,
      branchId: p.branchId,
      name: p.name,
      description: p.description,
      price: v.price,
      currency: p.currency,
      stockMethod: p.stockMethod,
      stockQuantity: v.stockQuantity,
      taxType: p.taxType,
      taxRate: p.taxRate,
      discount: p.discount,
      discountType: p.discountType,
      imageUrls: p.imageUrls,
      attributes: p.attributes,
      variations: p.variations,
      categoryId: p.categoryId,
    };
  });
}

const MOCK_PUBLIC_REVIEWS = MOCK_PRODUCTS.slice(0, 4).map((p, i) => ({
  id: 100 + i,
  title: `Great pick — ${p.name}`,
  rating: 5 - (i % 3),
  review: 'Mock review text for local development.',
  customerId: 'mock-customer',
  productId: p.id,
  imageUrls: [],
  createdAt: new Date(Date.now() - i * 86400000).toISOString(),
  updatedAt: new Date().toISOString(),
  createdBy: 'mock',
}));

function paginationMeta(page, size, total) {
  const totalPages = Math.max(1, Math.ceil(total / size));
  return {
    pageNumber: page,
    pageSize: size,
    totalElements: total,
    totalPages,
    first: page === 0,
    last: page >= totalPages - 1,
    sortField: 'name',
    sortOrder: 'ASC',
  };
}

function paginate(arr, page, size) {
  const p = Math.max(0, Number(page) || 0);
  const s = Math.min(100, Math.max(1, Number(size) || 20));
  const start = p * s;
  const content = arr.slice(start, start + s);
  return { content, metadata: paginationMeta(p, s, arr.length), isEmpty: content.length === 0 };
}

// --- Sessions (per token) -------------------------------------------------------------
const sessions = new Map();

function createSession(email) {
  return {
    email: email || 'dev@mock.local',
    username: 'mockuser',
    firstName: 'Mock',
    lastName: 'Customer',
    cartId: 1,
    branchId: MOCK_BRANCH_ID,
    cartItems: [],
    wishlist: new Map(),
    addresses: [
      {
        id: 1,
        isPrimary: true,
        primary: true,
        addressLine1: '1 Mock Street',
        addressLine2: '',
        addressLine3: '',
        addressLine4: '',
        city: 'Local',
        county: 'Dev',
        postcode: 'MO1 1CK',
        country: 'UK',
        latitude: 52.9167,
        longitude: -1.4667,
      },
    ],
    nextAddressId: 2,
    checkoutDraft: null,
    myReviews: [],
    nextReviewId: 1,
    orders: [],
    nextOrderNum: 1001,
    chats: [],
    nextChatId: 1,
    messagesByChat: new Map(),
  };
}

function getToken(req) {
  const raw = req.headers.cookie || '';
  const m = raw.match(/(?:^|;\s*)token=([^;]+)/);
  return m ? decodeURIComponent(m[1].trim()) : null;
}

function getSession(req) {
  const t = getToken(req);
  if (!t || !sessions.has(t)) return null;
  return sessions.get(t);
}

function requireSession(req, res) {
  const s = getSession(req);
  if (!s) {
    res.status(401).json({ message: 'No authentication token found' });
    return null;
  }
  return s;
}

function apiOk(data, message = 'OK') {
  return { success: true, message, data };
}

function cartTotal(items) {
  return items.reduce((sum, it) => sum + it.price * it.quantity, 0);
}

function buildCartItemFromVariant(product, variant, quantity) {
  const opts = variant.selectedOptions || {};
  const variantName = Object.entries(opts)
    .map(([k, v]) => `${k}: ${v}`)
    .join(', ');
  return {
    productId: product.id,
    variantId: variant.id,
    variantName: variantName || 'Default',
    quantity,
    price: variant.price,
    name: product.name,
    stockQuantity: variant.stockQuantity,
    stockMethod: product.stockMethod,
    description: product.description,
    imageUrls: product.imageUrls,
    currency: product.currency,
    selectedOptions: opts,
    inactive: false,
    available: true,
  };
}

function sessionCartToDetail(s) {
  const items = s.cartItems;
  return {
    id: s.cartId,
    totalPrice: cartTotal(items),
    cartStatus: 'ACTIVE',
    cartItems: items,
    branchId: s.branchId,
  };
}

function sessionCartToCheckoutDetail(s) {
  const items = s.cartItems.map((it, idx) => ({
    id: idx + 1,
    productId: it.productId,
    variantId: String(it.variantId),
    quantity: it.quantity,
    price: it.price,
    name: it.name,
    description: it.description || '',
    imageUrls: it.imageUrls || [],
    currency: it.currency,
  }));
  return {
    id: s.cartId,
    customerId: 1,
    accountNumber: 'MOCK-CUST',
    totalPrice: cartTotal(s.cartItems),
    cartItems: items,
    branchId: String(s.branchId),
  };
}

function openingHours() {
  const days = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'];
  return days.map((day, i) => ({
    branchId: MOCK_BRANCH_ID,
    dayOfWeek: day,
    openingTime: i === 6 ? '10:00:00' : '09:00:00',
    closingTime: i === 6 ? '16:00:00' : '18:00:00',
    isClosed: false,
  }));
}

const mockBranch = (id = 1) => ({
  id,
  accountNumber: 'MOCK-001',
  branchName: 'Mock Branch',
  branchCode: 'MB001',
  branchType: 'MAIN',
  branchStatus: 'ACTIVE',
  addressLine1: '1 Mock Street',
  addressLine2: '',
  addressLine3: '',
  addressLine4: '',
  city: 'Local',
  county: 'Dev',
  postcode: 'MO1 1CK',
  country: 'UK',
  latitude: 52.9167,
  longitude: -1.4667,
  contactNumber: '+440000000000',
  email: 'branch@mock.local',
});

const mockHero = () => ({
  storeName: 'Mock Store',
  storeDescription: 'Local development store',
  storeEmail: 'hello@mock.local',
  storePhone: '+440000000000',
  storeType: 'RETAIL',
  tagLine: 'Mock tagline',
  faviconUrl: '/favicon.ico',
  logoUrl: 'https://placehold.co/120x40/png?text=Logo',
  bannerUrl: 'https://placehold.co/1200x400/png?text=Banner',
});

const mockStoreWeb = (domain) => ({
  storeName: 'Mock Store',
  storeDescription: 'Local development store',
  storeEmail: 'hello@mock.local',
  storePhone: '+440000000000',
  storeType: 'RETAIL',
  addressLine1: '1 Mock Street',
  addressLine2: '',
  addressLine3: '',
  addressLine4: '',
  city: 'Local',
  county: 'Dev',
  postcode: 'MO1 1CK',
  country: 'UK',
  latitude: '52.9167',
  longitude: '-1.4667',
  branchName: 'Mock Branch',
  tagLine: 'Mock tagline',
  subHeading: 'Development',
  logo: 'https://placehold.co/120x40/png?text=Logo',
  bannerImage: 'https://placehold.co/1200x400/png?text=Banner',
  favicon: '/favicon.ico',
});

const mockStoreByDomain = (domain) => ({
  storeName: 'Mock Store',
  storeDescription: 'Local development store',
  tagLine: 'Mock tagline',
  domainName: domain || 'localhost',
  faviconUrl: '/favicon.ico',
  logoUrl: 'https://placehold.co/120x40/png?text=Logo',
  bannerUrl: 'https://placehold.co/1200x400/png?text=Banner',
});

const mockFooter = () => ({
  sections: [{ title: 'About', links: [{ label: 'Contact', href: '/contact' }] }],
  socialLinks: [{ name: 'Web', url: 'https://example.com' }],
});

// --- STOMP --------------------------------------------------------------------------
function stompFrame(command, headers, body = '') {
  let h = '';
  for (const [k, v] of Object.entries(headers)) {
    h += `${k}:${v}\n`;
  }
  return `${command}\n${h}\n${body}\x00`;
}

function parseStompFrame(raw) {
  const text = raw.replace(/\0$/, '');
  const firstNl = text.indexOf('\n');
  const command = firstNl >= 0 ? text.slice(0, firstNl) : text;
  let rest = firstNl >= 0 ? text.slice(firstNl + 1) : '';
  const headerEnd = rest.indexOf('\n\n');
  const headers = {};
  let body = '';
  if (headerEnd >= 0) {
    const headerPart = rest.slice(0, headerEnd);
    body = rest.slice(headerEnd + 2);
    headerPart.split('\n').forEach((line) => {
      const idx = line.indexOf(':');
      if (idx > 0) headers[line.slice(0, idx)] = line.slice(idx + 1);
    });
  } else {
    rest.split('\n').forEach((line) => {
      if (line === '') return;
      const idx = line.indexOf(':');
      if (idx > 0) headers[line.slice(0, idx)] = line.slice(idx + 1);
    });
  }
  return { command, headers, body };
}

function attachStomp(ws) {
  let buf = '';

  const sendConnected = () => {
    ws.send(
      stompFrame('CONNECTED', {
        version: '1.2',
        'heart-beat': '3000,3000',
        server: 'mystic-flame-mock/1.0',
      }),
    );
  };

  const maybeSendNotificationBootstrap = (subscriptionId, destination) => {
    if (destination === '/user/queue/notifications' && subscriptionId) {
      ws.send(
        stompFrame(
          'MESSAGE',
          {
            subscription: subscriptionId,
            'message-id': 'mock-notif-1',
            destination: '/user/queue/notifications',
            'content-type': 'application/json',
          },
          '0',
        ),
      );
    }
  };

  ws.on('message', (data, isBinary) => {
    if (isBinary) return;
    const s = data.toString('utf8');
    if (s === '\n') {
      ws.send('\n');
      return;
    }

    buf += s;
    const parts = buf.split('\0');
    buf = parts.pop() || '';

    for (const chunk of parts) {
      if (!chunk || chunk === '\n') continue;
      const { command, headers, body } = parseStompFrame(chunk + '\0');

      switch (command) {
        case 'CONNECT':
        case 'STOMP':
          sendConnected();
          break;
        case 'SUBSCRIBE': {
          const subId = headers.id;
          const dest = headers.destination;
          maybeSendNotificationBootstrap(subId, dest);
          break;
        }
        case 'DISCONNECT':
          ws.close();
          break;
        case 'SEND':
        case 'ACK':
        case 'NACK':
        case 'UNSUBSCRIBE':
          break;
        default:
          if (command) console.warn('[mock STOMP] unhandled command:', command);
      }
    }
  });
}

// --- Express app --------------------------------------------------------------------
function registerRoutes(app, prefix) {
  const participant = (s, type = 'CUSTOMER') => ({
    id: 1,
    username: s.username,
    nickname: s.firstName,
    participantType: type,
    status: 'ONLINE',
    firstName: s.firstName,
    lastName: s.lastName,
    profileImageUrl: null,
  });

  const emptyMessagesPage = () => ({
    content: [],
    metadata: paginationMeta(0, 10, 0),
    isEmpty: true,
  });

  // ----- Public -----
  app.get(`${prefix}/public/storeWeb`, (req, res) => {
    res.json(mockStoreWeb(req.query.domainName || 'localhost'));
  });

  app.get(`${prefix}/public/customer-gateway/heroes/:domain`, (_req, res) => {
    res.json(mockHero());
  });

  app.get(`${prefix}/public/customer-gateway/stores/:domain`, (req, res) => {
    res.json(mockStoreByDomain(req.params.domain));
  });

  app.get(`${prefix}/public/customer-gateway/featured-products/:domain`, (_req, res) => {
    res.json(featuredProductDetails());
  });

  app.get(`${prefix}/public/customer-gateway/featured-categories/:domain`, (_req, res) => {
    res.json(
      MOCK_CATEGORIES.filter((c) => c.featured).map((c) => ({
        id: c.id,
        branchId: c.branchId,
        name: c.name,
        description: c.description || '',
        imageUrl: c.imageUrl || '',
      })),
    );
  });

  app.get(`${prefix}/public/customer-gateway/branches/domain/:domain`, (_req, res) => {
    res.json([mockBranch(1)]);
  });

  app.get(`${prefix}/public/customer-gateway/branches/v2/domain/:domain`, (_req, res) => {
    const b = mockBranch(1);
    res.json({ branches: [b], nearest: b });
  });

  app.get(`${prefix}/public/customer-gateway/footer/:branchId`, (_req, res) => {
    res.json(mockFooter());
  });

  app.get(`${prefix}/public/customer-gateway/branches/:branchId/hours`, (_req, res) => {
    res.json(openingHours());
  });

  app.get(`${prefix}/public/customer-gateway/branches/:branchId/status`, (req, res) => {
    const now = new Date().toISOString();
    res.json({
      branchId: String(req.params.branchId),
      branchName: 'Mock Branch',
      hasOpeningHours: true,
      isOpen: true,
      currentTime: now,
      timeUntilStateChange: 3600000,
      nextStateChangeTime: now,
      nextTransition: 'UNDEFINED',
      formattedTimeUntilStateChange: '—',
    });
  });

  app.get(`${prefix}/public/customer-gateway/payment/payment-details/:domain`, (_req, res) => {
    res.json({
      codEnabled: true,
      onlinePaymentEnabled: true,
      onlinePaymentGateway: 'STRIPE',
    });
  });

  app.get(`${prefix}/public/customer-gateway/fulfillment/fulfillment-summary/:domain`, (_req, res) => {
    res.json({
      selfPickupEnabled: true,
      deliveryEnabled: true,
      deliveryAvailable: true,
    });
  });

  app.get(`${prefix}/public/customer-gateway/branches/:branchId/categories`, (req, res) => {
    const page = Number(req.query.page) || 0;
    const size = Number(req.query.size) || 100;
    res.json(paginate(MOCK_CATEGORIES, page, size));
  });

  app.get(`${prefix}/public/customer-gateway/branches/:branchId/products/featured`, (_req, res) => {
    res.json(MOCK_PRODUCTS.filter((p) => p.featured));
  });

  app.get(`${prefix}/public/customer-gateway/branches/:branchId/products`, (req, res) => {
    let list = [...MOCK_PRODUCTS];
    const catIds = (req.query.categoryIds || '')
      .split(',')
      .map((x) => x.trim())
      .filter(Boolean)
      .map(Number);
    if (catIds.length) {
      list = list.filter((p) => catIds.includes(p.categoryId));
    }
    const q = (req.query.search || '').toLowerCase();
    if (q) list = list.filter((p) => p.name.toLowerCase().includes(q) || p.description.toLowerCase().includes(q));
    const page = Number(req.query.page) || 0;
    const size = Number(req.query.size) || 20;
    res.json(paginate(list, page, size));
  });

  app.get(`${prefix}/public/customer-gateway/domains/:domain/products`, (req, res) => {
    const q = (req.query.query || '').toLowerCase();
    let list = [...MOCK_PRODUCTS];
    if (q) list = list.filter((p) => p.name.toLowerCase().includes(q));
    res.json(list);
  });

  app.get(`${prefix}/public/customer-gateway/products/related-products/:productId`, (req, res) => {
    const cur = productById(req.params.productId);
    const list = MOCK_PRODUCTS.filter((p) => p.id !== req.params.productId && (!cur || p.categoryId === cur.categoryId)).slice(0, 3);
    res.json(list.length ? list : MOCK_PRODUCTS.slice(0, 2));
  });

  app.get(`${prefix}/public/customer-gateway/products/:productId`, (req, res) => {
    const p = productById(req.params.productId);
    if (!p) return res.status(404).json({ message: 'Product not found' });
    res.json(p);
  });

  app.post(`${prefix}/public/customer-gateway/chat/create`, (_req, res) => {
    res.json({
      chatId: 1,
      token: 'mock-chat-token',
    });
  });

  app.get(`${prefix}/public/customer-gateway/chat/:chatId`, (req, res) => {
    const now = new Date().toISOString();
    const anon = {
      id: 1,
      username: 'guest',
      nickname: 'Guest',
      participantType: 'ANONYMOUS',
      status: 'ONLINE',
    };
    res.json({
      id: Number(req.params.chatId),
      branchId: MOCK_BRANCH_ID,
      chatType: 'ANONYMOUS',
      title: 'Mock chat',
      startDate: now,
      closed: false,
      archived: false,
      customer: anon,
      branchManagers: [],
      messages: [],
    });
  });

  app.post(`${prefix}/public/customer-gateway/message/send`, (_req, res) => {
    res.json({
      id: 1,
      status: 'SENT',
      content: 'ok',
      timestamp: new Date().toISOString(),
      chatId: 1,
      sender: {
        id: 1,
        username: 'guest',
        participantType: 'ANONYMOUS',
        status: 'ONLINE',
      },
      attachments: [],
    });
  });

  app.get(`${prefix}/public/customer-gateway/message/latest`, (_req, res) => {
    res.json(emptyMessagesPage());
  });

  app.get(`${prefix}/public/customer-gateway/order/:orderNumber/track`, (req, res) => {
    const n = req.params.orderNumber.replace(/^#/, '');
    res.json({
      orderNumber: n,
      orderStatus: 'ORDER_PLACED',
      orderDate: new Date().toISOString(),
      totalAmount: '49.99',
      currency: 'GBP',
      branchName: 'Mock Branch',
      branchAddress: '1 Mock Street, Local, MO1 1CK',
      cancellationRequested: false,
      refundRequested: false,
    });
  });

  app.get(`${prefix}/public/customer-gateway/reviews/:reviewId`, (req, res) => {
    const id = Number(req.params.reviewId);
    const r = MOCK_PUBLIC_REVIEWS.find((x) => x.id === id);
    if (!r) return res.status(404).json({ message: 'Mock: review not found' });
    res.json(r);
  });

  app.get(`${prefix}/public/customer-gateway/reviews/product/:productId`, (req, res) => {
    const list = MOCK_PUBLIC_REVIEWS.filter((r) => r.productId === req.params.productId);
    const page = Number(req.query.page) || 0;
    const size = Number(req.query.size) || 10;
    res.json(paginate(list, page, size));
  });

  app.get(`${prefix}/public/customer-gateway/reviews/product/:productId/average-rating`, (req, res) => {
    const list = MOCK_PUBLIC_REVIEWS.filter((r) => r.productId === req.params.productId);
    if (!list.length) return res.json(0);
    const avg = list.reduce((a, b) => a + b.rating, 0) / list.length;
    res.json(Number(avg.toFixed(2)));
  });

  app.get(`${prefix}/public/customer-gateway/reviews/product/:productId/rating-distribution`, (req, res) => {
    const list = MOCK_PUBLIC_REVIEWS.filter((r) => r.productId === req.params.productId);
    const dist = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    list.forEach((r) => {
      const k = Math.min(5, Math.max(1, Math.round(r.rating)));
      dist[k] += 1;
    });
    res.json(dist);
  });

  app.get(`${prefix}/public/customer-gateway/reviews/recent`, (req, res) => {
    const page = Number(req.query.page) || 0;
    const size = Number(req.query.size) || 10;
    res.json(paginate([...MOCK_PUBLIC_REVIEWS].sort((a, b) => b.createdAt.localeCompare(a.createdAt)), page, size));
  });

  app.get(`${prefix}/public/customer-gateway/reviews/top-rated`, (req, res) => {
    const page = Number(req.query.page) || 0;
    const size = Number(req.query.size) || 10;
    const sorted = [...MOCK_PUBLIC_REVIEWS].sort((a, b) => b.rating - a.rating);
    res.json(paginate(sorted, page, size));
  });

  app.get(`${prefix}/public/customer-gateway/reviews/by-rating`, (req, res) => {
    const rating = Number(req.query.rating) || 5;
    const page = Number(req.query.page) || 0;
    const size = Number(req.query.size) || 10;
    const filtered = MOCK_PUBLIC_REVIEWS.filter((r) => r.rating === rating);
    res.json(paginate(filtered, page, size));
  });

  // ----- Auth (no session yet) -----
  function authCookieResponse(res, email) {
    const token = `mock-${crypto.randomBytes(12).toString('hex')}`;
    sessions.set(token, createSession(email));
    res.setHeader('Set-Cookie', `token=${token}; Path=/; SameSite=Lax; Max-Age=86400`);
    res.json({ success: true, message: 'Logged in (mock)' });
  }

  app.post(`${prefix}/auth-customer/email/login/:domain`, (req, res) => {
    const email = (req.body && req.body.email) || 'dev@mock.local';
    authCookieResponse(res, email);
  });

  app.post(`${prefix}/auth-customer/email/signup/:domain`, (req, res) => {
    res.json({ success: true, message: 'Signup started (mock)' });
  });

  app.post(`${prefix}/auth-customer/email/verify/:domain`, (_req, res) => {
    res.json({ success: true, message: 'Verified (mock)' });
  });

  app.post(`${prefix}/auth/email/reset-password`, (_req, res) => {
    res.json({ success: true, message: 'Reset email sent (mock)' });
  });

  app.post(`${prefix}/auth-customer/whatsapp/login/otp/:domain`, (_req, res) => {
    res.json({ success: true, message: 'OTP sent (mock)' });
  });

  app.post(`${prefix}/auth-customer/whatsapp/login/verify/:domain`, (req, res) => {
    const phone = (req.body && req.body.phoneNumber) || 'mock';
    authCookieResponse(res, `${phone}@mock.local`);
  });

  app.post(`${prefix}/auth-customer/whatsapp/signup/:domain`, (_req, res) => {
    res.json({ success: true, message: 'WhatsApp signup (mock)' });
  });

  app.post(`${prefix}/auth-customer/whatsapp/signup/complete/:domain`, (req, res) => {
    authCookieResponse(res, 'whatsapp@mock.local');
  });

  // ----- Customer (session) -----
  app.get(`${prefix}/customer/user-info`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json({
      username: s.username,
      firstName: s.firstName,
      lastName: s.lastName,
      email: s.email,
    });
  });

  app.post(`${prefix}/customer/logout`, (req, res) => {
    const t = getToken(req);
    if (t) sessions.delete(t);
    res.setHeader('Set-Cookie', 'token=; Path=/; Max-Age=0');
    res.json({ success: true });
  });

  app.get(`${prefix}/customer/carts`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json(apiOk(sessionCartToDetail(s)));
  });

  app.get(`${prefix}/customer/carts/items/count`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const count = s.cartItems.reduce((a, it) => a + it.quantity, 0);
    res.json(apiOk(count));
  });

  app.post(`${prefix}/customer/carts/items`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const { productId, quantity, variantId } = req.body || {};
    const found = variantByIds(productId, variantId);
    if (!found) return res.status(400).json({ message: 'Invalid product or variant' });
    const { product, variant } = found;
    const existing = s.cartItems.find((it) => it.productId === productId && it.variantId === variantId);
    if (existing) existing.quantity += quantity;
    else s.cartItems.push(buildCartItemFromVariant(product, variant, quantity));
    res.json(apiOk(sessionCartToDetail(s)));
  });

  app.delete(`${prefix}/customer/carts/items`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const { productId, variantId } = req.body || {};
    s.cartItems = s.cartItems.filter((it) => !(it.productId === productId && it.variantId === variantId));
    res.json(apiOk(sessionCartToDetail(s)));
  });

  app.put(`${prefix}/customer/carts/items`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const { productId, quantity, variantId } = req.body || {};
    const it = s.cartItems.find((i) => i.productId === productId && i.variantId === variantId);
    if (!it) return res.status(404).json({ message: 'Item not in cart' });
    it.quantity = quantity;
    res.json(apiOk(sessionCartToDetail(s)));
  });

  app.get(`${prefix}/customer/wishlist`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const data = [...s.wishlist.values()];
    res.json(apiOk(data));
  });

  app.post(`${prefix}/customer/wishlist/:productId`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const p = productById(req.params.productId);
    if (!p) return res.status(404).json({ message: 'Product not found' });
    s.wishlist.set(p.id, {
      wishlistId: `w-${p.id}`,
      customerId: 'mock',
      productId: p.id,
      productName: p.name,
      productImages: p.imageUrls || [],
    });
    res.json(apiOk(undefined, 'Added'));
  });

  app.delete(`${prefix}/customer/wishlist/:productId`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    s.wishlist.delete(req.params.productId);
    res.json(apiOk(undefined, 'Removed'));
  });

  app.delete(`${prefix}/customer/wishlist/clear`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    s.wishlist.clear();
    res.json(apiOk(undefined, 'Cleared'));
  });

  app.get(`${prefix}/customer/customer-address`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json(s.addresses);
  });

  app.get(`${prefix}/customer/customer-address/primary`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json(s.addresses.find((a) => a.isPrimary) || s.addresses[0]);
  });

  app.post(`${prefix}/customer/customer-address`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const body = req.body || {};
    const id = s.nextAddressId++;
    const addr = {
      id,
      isPrimary: !!body.isPrimary,
      primary: !!body.isPrimary,
      addressLine1: body.addressLine1,
      addressLine2: body.addressLine2 || '',
      addressLine3: body.addressLine3 || '',
      addressLine4: body.addressLine4 || '',
      city: body.city,
      county: body.county,
      postcode: body.postcode || '',
      country: body.country,
      latitude: body.latitude,
      longitude: body.longitude,
    };
    if (addr.isPrimary) s.addresses.forEach((a) => { a.isPrimary = false; a.primary = false; });
    s.addresses.push(addr);
    res.json(addr);
  });

  app.put(`${prefix}/customer/customer-address/:addressId`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const id = Number(req.params.addressId);
    const a = s.addresses.find((x) => x.id === id);
    if (!a) return res.status(404).json({ message: 'Not found' });
    Object.assign(a, req.body, { id });
    res.json(a);
  });

  app.delete(`${prefix}/customer/customer-address/:addressId`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const id = Number(req.params.addressId);
    s.addresses = s.addresses.filter((x) => x.id !== id);
    res.status(204).send();
  });

  app.post(`${prefix}/customer/checkout/initiate`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    s.checkoutDraft = req.body || {};
    res.json({ ok: true });
  });

  app.get(`${prefix}/customer/checkout`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const draft = s.checkoutDraft || {};
    const addr = s.addresses.find((a) => String(a.id) === String(draft.customerAddressId)) || s.addresses[0];
    const subtotal = cartTotal(s.cartItems);
    const deliveryFee = draft.fulfillmentMethod === 'DELIVERY' ? 4.99 : 0;
    const taxAmount = Number((subtotal * 0.2).toFixed(2));
    const promotionDiscount = 0;
    const totalAmount = Number((subtotal + deliveryFee + taxAmount - promotionDiscount).toFixed(2));

    res.json({
      paymentMethod: draft.paymentMethod || 'CARD',
      fulfillmentMethod: draft.fulfillmentMethod || 'COLLECTION',
      deliveryAddress:
        draft.fulfillmentMethod === 'DELIVERY' && addr
          ? {
              id: addr.id,
              addressDescription: 'Home',
              addressLine1: addr.addressLine1,
              addressLine2: addr.addressLine2 || '',
              addressLine3: addr.addressLine3 || '',
              addressLine4: addr.addressLine4 || '',
              city: addr.city,
              county: addr.county,
              postcode: addr.postcode || '',
              country: addr.country,
              latitude: addr.latitude,
              longitude: addr.longitude,
              specialInstructions: draft.notes || '',
            }
          : undefined,
      promotionCode: draft.promotionCode || '',
      cartDetail: sessionCartToCheckoutDetail(s),
      promotionDiscount,
      deliveryFee,
      taxAmount,
      totalAmount,
    });
  });

  app.post(`${prefix}/customer/checkout/payment/initiate`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const subtotal = cartTotal(s.cartItems);
    const draft = s.checkoutDraft || {};
    const deliveryFee = draft.fulfillmentMethod === 'DELIVERY' ? 4.99 : 0;
    const total = Number((subtotal + deliveryFee + subtotal * 0.2).toFixed(2));
    res.json({
      currency: 'GBP',
      totalAmount: total,
      paymentMethod: draft.paymentMethod || 'CARD',
      paymentProvider: 'STRIPE',
      clientSecret: null,
      razorpayOrderId: null,
    });
  });

  app.post(`${prefix}/customer/promotion/calculate`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const code = (req.body && req.body.promotionCode) || '';
    const subtotal = cartTotal(s.cartItems);
    if (!code || code.toUpperCase() === 'INVALID') {
      return res.status(400).json({
        promotionCode: code,
        result: 'INVALID_PROMOTION',
        message: 'This promotion is not available',
        discountAmount: 0,
        finalOrderAmount: subtotal,
        cartId: String(s.cartId),
      });
    }
    const discountAmount = Number((subtotal * 0.1).toFixed(2));
    res.json({
      promotionCode: code,
      result: 'SUCCESS',
      message: 'Promotion applied successfully',
      discountAmount,
      finalOrderAmount: Number((subtotal - discountAmount).toFixed(2)),
      cartId: String(s.cartId),
    });
  });

  app.get(`${prefix}/customer/delivery/cart/cost`, (_req, res) => {
    const s = requireSession(_req, res);
    if (!s) return;
    res.json({
      zoneId: 1,
      zoneName: 'Mock Zone',
      zoneType: 'FIXED',
      outOfZone: false,
      deliveryFee: 4.99,
      calculatedAt: new Date().toISOString(),
      freeDelivery: false,
      meetsMinOrderAmount: true,
      minFreeDeliveryAmount: 50,
      hasDeliveryTime: true,
      minDeliveryTimeValue: 30,
      maxDeliveryTimeValue: 60,
      deliveryTimeUnit: 'MINUTES',
      orderProcessingTime: 1,
      orderProcessingTimeUnit: 'HOURS',
    });
  });

  app.get(`${prefix}/customer/fulfillment/pickup-locations/:domain`, (_req, res) => {
    res.json([
      {
        branchName: 'Mock Branch',
        addressLine1: '1 Mock Street',
        addressLine2: null,
        city: 'Local',
        county: 'Dev',
        postalCode: 'MO1 1CK',
        country: 'UK',
        orderProcessingTime: 1,
        orderProcessingTimeUnit: 'HOURS',
      },
    ]);
  });

  app.post(`${prefix}/customer/order/validateStocks/cart/:cartId`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json({ valid: true, cartId: req.params.cartId });
  });

  app.post(`${prefix}/customer/order/place`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    if (!s.cartItems.length) return res.status(400).json({ message: 'Cart is empty' });
    const orderNum = String(s.nextOrderNum++);
    const order = {
      id: s.orders.length + 1,
      orderNumber: orderNum,
      cartId: s.cartId,
      branchId: s.branchId,
      customerId: 1,
      branchName: 'Mock Branch',
      branchAddress: '1 Mock Street, Local MO1 1CK',
      customerName: `${s.firstName} ${s.lastName}`,
      customerAddress: null,
      customerEmail: s.email,
      customerPhone: '+440000000000',
      orderDate: new Date().toISOString(),
      totalAmount: String(cartTotal(s.cartItems)),
      currency: 'GBP',
      orderStatus: 'ORDER_PLACED',
      orderItems: s.cartItems.map((it) => ({
        productId: it.productId,
        variantId: it.variantId,
        quantity: it.quantity,
        price: String(it.price),
        name: it.name,
        variantName: it.variantName,
        description: it.description || '',
        imageUrls: it.imageUrls || [],
        currency: it.currency,
      })),
      orderHistory: [
        {
          id: 1,
          previousStatus: null,
          newStatus: 'ORDER_PLACED',
          changedAt: new Date().toISOString(),
          changedBy: 'system',
          notes: null,
        },
      ],
      cancellationRequested: false,
      refundRequested: false,
      cancellationFee: '0',
      refundFee: '0',
      paymentMethod: 'CARD',
      orderReference: null,
    };
    s.orders.unshift(order);
    s.cartItems = [];
    res.json({ success: true, orderNumber: orderNum });
  });

  app.post(`${prefix}/customer/order/create`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json({ success: true, message: 'Order create (mock)', data: req.body });
  });

  app.get(`${prefix}/customer/order/active`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const active = s.orders.filter((o) =>
      ['PENDING', 'PAID', 'ORDER_PLACED', 'PREPARING', 'OUT_FOR_DELIVERY', 'WAITING_FOR_PICKUP'].includes(o.orderStatus),
    );
    res.json(active);
  });

  app.get(`${prefix}/customer/order/completed`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const done = s.orders.filter((o) => ['COMPLETED', 'CANCELLED', 'REFUNDED'].includes(o.orderStatus));
    res.json(done);
  });

  app.get(`${prefix}/customer/order`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json(s.orders);
  });

  app.get(`${prefix}/customer/order/:id/track`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const o = s.orders.find((x) => String(x.id) === String(req.params.id));
    if (!o) return res.status(404).json({ message: 'Order not found' });
    res.json({
      orderNumber: o.orderNumber,
      orderStatus: o.orderStatus,
      orderDate: o.orderDate,
      totalAmount: o.totalAmount,
      currency: o.currency,
      branchName: o.branchName,
      branchAddress: o.branchAddress,
      cancellationRequested: o.cancellationRequested,
      refundRequested: o.refundRequested,
    });
  });

  app.post(`${prefix}/customer/order/:id/requestCancellation`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const o = s.orders.find((x) => String(x.id) === String(req.params.id));
    if (!o) return res.status(404).json({ message: 'Not found' });
    o.cancellationRequested = true;
    res.json({ success: true });
  });

  app.post(`${prefix}/customer/order/:id/requestRefund`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const o = s.orders.find((x) => String(x.id) === String(req.params.id));
    if (!o) return res.status(404).json({ message: 'Not found' });
    o.refundRequested = true;
    res.json({ success: true });
  });

  app.post(`${prefix}/customer/order/:id/repeat`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const o = s.orders.find((x) => String(x.id) === String(req.params.id));
    if (!o) return res.status(404).json({ message: 'Not found' });
    for (const line of o.orderItems) {
      const p = productById(line.productId);
      if (!p) continue;
      const vid = line.variantId != null ? Number(line.variantId) : p.variants[0].id;
      const variant = p.variants.find((v) => v.id === vid) || p.variants[0];
      const existing = s.cartItems.find((it) => it.productId === p.id && it.variantId === variant.id);
      if (existing) existing.quantity += line.quantity;
      else s.cartItems.push(buildCartItemFromVariant(p, variant, line.quantity));
    }
    res.json(apiOk(sessionCartToDetail(s)));
  });

  app.get(`${prefix}/customer/order/:id/receipt`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json({ url: `https://placehold.co/600x800/png?text=Receipt+${req.params.id}` });
  });

  app.get(`${prefix}/customer/order/:id/invoice`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json({ url: `https://placehold.co/600x800/png?text=Invoice+${req.params.id}` });
  });

  app.post(`${prefix}/customer/verify-payment`, (_req, res) => {
    res.json({ success: true });
  });

  app.get(`${prefix}/customer/stripe/config`, (_req, res) => {
    res.json({
      publishableKey: process.env.MOCK_STRIPE_PUBLISHABLE_KEY || 'pk_test_51234567890',
      connectedAccountId: null,
    });
  });

  // Reviews (authenticated)
  app.get(`${prefix}/customer/reviews/my`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const page = Number(req.query.page) || 0;
    const size = Number(req.query.size) || 10;
    res.json(paginate(s.myReviews, page, size));
  });

  app.get(`${prefix}/customer/reviews/recent`, (req, res) => {
    if (!requireSession(req, res)) return;
    const page = Number(req.query.page) || 0;
    const size = Number(req.query.size) || 10;
    res.json(paginate([...MOCK_PUBLIC_REVIEWS].sort((a, b) => b.createdAt.localeCompare(a.createdAt)), page, size));
  });

  app.get(`${prefix}/customer/reviews/top-rated`, (req, res) => {
    if (!requireSession(req, res)) return;
    const page = Number(req.query.page) || 0;
    const size = Number(req.query.size) || 10;
    const sorted = [...MOCK_PUBLIC_REVIEWS].sort((a, b) => b.rating - a.rating);
    res.json(paginate(sorted, page, size));
  });

  app.get(`${prefix}/customer/reviews/product/:productId/has-reviewed`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const has = s.myReviews.some((r) => r.productId === req.params.productId);
    res.json(has);
  });

  app.post(`${prefix}/customer/reviews/:id`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const productId = req.params.id;
    const p = productById(productId);
    if (!p) return res.status(404).json({ message: 'Product not found' });
    const id = s.nextReviewId++;
    const row = {
      id,
      title: 'Mock review',
      rating: 5,
      review: 'Great (mock)',
      customerId: 'me',
      productId,
      imageUrls: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    s.myReviews.push(row);
    res.json(row);
  });

  app.put(`${prefix}/customer/reviews/:id`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const id = Number(req.params.id);
    const row = s.myReviews.find((r) => r.id === id);
    if (!row) return res.status(404).json({ message: 'Not found' });
    row.updatedAt = new Date().toISOString();
    res.json(row);
  });

  app.delete(`${prefix}/customer/reviews/:id`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const id = Number(req.params.id);
    s.myReviews = s.myReviews.filter((r) => r.id !== id);
    res.status(204).send();
  });

  // Chat (authenticated)
  app.get(`${prefix}/customer/participants/me`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json(participant(s));
  });

  app.put(`${prefix}/customer/participants/nickname`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const nick = req.query.nickname || 'You';
    s.firstName = nick;
    res.json(participant(s));
  });

  app.post(`${prefix}/customer/chats/create`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const branchId = Number(req.query.branchId) || MOCK_BRANCH_ID;
    const id = s.nextChatId++;
    const now = new Date().toISOString();
    const chat = {
      id,
      branchId,
      chatType: 'CUSTOMER_TO_BRANCH_MANAGER',
      title: 'Support',
      startDate: now,
      closed: false,
      archived: false,
      customer: participant(s),
      branchManagers: [],
      messages: [],
    };
    s.chats.push(chat);
    s.messagesByChat.set(id, []);
    res.json(chat);
  });

  app.get(`${prefix}/customer/chats/:chatId`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const chat = s.chats.find((c) => String(c.id) === String(req.params.chatId));
    if (!chat) return res.status(404).json({ message: 'Not found' });
    res.json(chat);
  });

  app.get(`${prefix}/customer/chats`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const page = Number(req.query.page) || 0;
    const size = Number(req.query.size) || 10;
    res.json(paginate(s.chats, page, size));
  });

  app.post(`${prefix}/customer/messages/send`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json({
      id: Date.now(),
      status: 'SENT',
      content: 'mock',
      timestamp: new Date().toISOString(),
      chatId: 1,
      sender: participant(s),
      attachments: [],
    });
  });

  app.get(`${prefix}/customer/messages/getByChat`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    const chatId = Number(req.query.chatId);
    const list = s.messagesByChat.get(chatId) || [];
    const page = Number(req.query.page) || 0;
    const size = Number(req.query.size) || 10;
    res.json(paginate(list, page, size));
  });

  app.get(`${prefix}/customer/messages/unread-count`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json(0);
  });

  app.post(`${prefix}/customer/messages/:messageId/read`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json({ id: Number(req.params.messageId), status: 'READ' });
  });

  app.post(`${prefix}/customer/messages/:messageId/receive`, (req, res) => {
    const s = requireSession(req, res);
    if (!s) return;
    res.json({ id: Number(req.params.messageId), status: 'DELIVERED' });
  });

  app.post(`${prefix}/customer/messages/read-all`, (req, res) => {
    if (!requireSession(req, res)) return;
    res.json({ ok: true });
  });

  app.post(`${prefix}/customer/messages/read-all/:chatId`, (req, res) => {
    if (!requireSession(req, res)) return;
    res.json({ ok: true });
  });

  app.get(`${prefix}/health`, (_req, res) => {
    res.json({ ok: true, service: 'mystic-flame-mock-backend' });
  });
}

function main() {
  const app = express();
  app.use(cors({ origin: true, credentials: true }));
  app.use(express.json({ limit: '2mb' }));
  app.use(express.urlencoded({ extended: true }));

  const prefix = '/api/v1';
  registerRoutes(app, prefix);

  app.use(`${prefix}`, (req, res) => {
    console.warn('[mock-backend] unhandled', req.method, req.originalUrl);
    res.status(501).json({
      message: 'Not implemented in mock-backend — add a route in mock-backend/server.js',
      path: req.path,
      method: req.method,
    });
  });

  const server = http.createServer(app);

  const wss = new WebSocketServer({ noServer: true });

  server.on('upgrade', (request, socket, head) => {
    const host = request.headers.host || 'localhost';
    const pathname = new URL(request.url, `http://${host}`).pathname.replace(/\/{2,}/g, '/');
    if (pathname === '/api/v1/ws-endpoint' || pathname.endsWith('/api/v1/ws-endpoint')) {
      wss.handleUpgrade(request, socket, head, (ws) => {
        wss.emit('connection', ws, request);
      });
    } else {
      socket.destroy();
    }
  });

  wss.on('connection', (ws) => {
    attachStomp(ws);
  });

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.error(
        `[mock-backend] Port ${PORT} is already in use (another mock-backend or app is listening).`,
      );
      console.error(`  Free it:  kill $(lsof -t -i:${PORT})   or   fuser -k ${PORT}/tcp`);
      console.error(
        `  Or use a different port: MOCK_BACKEND_PORT=8081 and set NEXT_PUBLIC_API_BASE_URL / NEXT_PUBLIC_API_BASE in .env to match.`,
      );
      process.exit(1);
    }
    throw err;
  });

  server.listen(PORT, () => {
    console.log(`[mock-backend] http://localhost:${PORT} (API ${prefix}, WS ${prefix}/ws-endpoint)`);
  });
}

main();
