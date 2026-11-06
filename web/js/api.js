// Same-origin client for /api: JSON in and out, one error type for every failure (including Retry-After), and a hook that reports X-App-Version and X-Served-By of each response.

export class ApiError extends Error {
  /**
   * @param {number} status      HTTP status, or 0 when the request never got an answer.
   * @param {string} code        API code (R1-R7, VALIDATION, NOT_FOUND, ROOM_STATUS, UNAVAILABLE) or a client code
   *                             (NETWORK, BAD_RESPONSE, HTTP_<status>).
   * @param {string} message
   * @param {number|null} retryAfter  Seconds from the Retry-After header, when the API sent one.
   */
  constructor(status, code, message, retryAfter = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
  }
}

const responseListeners = new Set();

/** Subscribes to metadata of every API response: `{ version, pod, status }`. */
export function onResponse(listener) {
  responseListeners.add(listener);
}

function report(response) {
  const meta = {
    version: response.headers.get('X-App-Version'),
    pod: response.headers.get('X-Served-By'),
    status: response.status,
  };
  for (const listener of responseListeners) listener(meta);
}

/** Retry-After as seconds; the header may hold seconds or an HTTP date. */
function retryAfterSeconds(response) {
  const header = response.headers.get('Retry-After');
  if (!header) return null;
  const seconds = Number(header);
  if (Number.isFinite(seconds)) return Math.max(0, seconds);
  const date = Date.parse(header);
  return Number.isNaN(date) ? null : Math.max(0, Math.round((date - Date.now()) / 1000));
}

function fallbackMessage(status) {
  if (status === 502 || status === 503 || status === 504) return `The API is unavailable (HTTP ${status}).`;
  if (status >= 500) return `The API failed with HTTP ${status}.`;
  return `The request failed with HTTP ${status}.`;
}

async function readJson(response) {
  const type = response.headers.get('Content-Type') ?? '';
  if (!type.includes('application/json')) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function request(method, path, body) {
  const init = { method, headers: { Accept: 'application/json' }, cache: 'no-store' };
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(0, 'NETWORK', 'The API could not be reached.');
  }

  report(response);
  const data = await readJson(response);
  if (!response.ok) {
    const error = data?.error;
    throw new ApiError(
      response.status,
      error?.code ?? `HTTP_${response.status}`,
      error?.message ?? fallbackMessage(response.status),
      retryAfterSeconds(response),
    );
  }
  // Every endpoint answers JSON; anything else (an HTML page from a misrouted proxy, say) is a failure, not data.
  if (data === null || typeof data !== 'object') {
    throw new ApiError(response.status, 'BAD_RESPONSE', `${method} ${path} did not return JSON.`);
  }
  return data;
}

/** A list endpoint: `{"items": [...], "count": n}`. Returns the items, or fails before any caller sees a bad body. */
async function list(path) {
  const data = await request('GET', path);
  if (!Array.isArray(data.items)) {
    throw new ApiError(200, 'BAD_RESPONSE', `GET ${path} returned a body without an items list.`);
  }
  return data.items;
}

const encode = encodeURIComponent;

export const api = {
  rooms: () => list('/rooms'),
  arrivals: () => list('/front-desk/arrivals'),
  departures: () => list('/front-desk/departures'),
  inHouse: () => list('/front-desk/in-house'),

  /** The latest night audit report, or null before the first audit (404). */
  async latestAudit() {
    try {
      return await request('GET', '/night-audit/reports/latest');
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },

  setRoomStatus: (number, status) => request('PATCH', `/rooms/${encode(number)}`, { status }),
  createReservation: (reservation) => request('POST', '/reservations', reservation),
  checkIn: (id, party) => request('POST', `/reservations/${encode(id)}/check-in`, party),
  checkOut: (id) => request('POST', `/reservations/${encode(id)}/check-out`),
  cancel: (id) => request('POST', `/reservations/${encode(id)}/cancel`),
};
