interface AttemptBucket {
  count: number;
  resetAt: number;
}

export interface RateLimitSettings {
  maxAttempts: number;
  windowSeconds: number;
}

export class LoginRateLimiter {
  private readonly attempts = new Map<string, AttemptBucket>();

  constructor(private readonly maxEntries = 500) {}

  check(key: string, settings: RateLimitSettings, now = Date.now()) {
    this.prune(now);
    const bucket = this.attempts.get(key);
    if (!bucket || bucket.resetAt <= now || bucket.count < settings.maxAttempts) {
      return { allowed: true, retryAfterSeconds: 0 };
    }
    return {
      allowed: false,
      retryAfterSeconds: Math.max(1, Math.ceil((bucket.resetAt - now) / 1000)),
    };
  }

  recordFailure(key: string, settings: RateLimitSettings, now = Date.now()) {
    this.prune(now);
    const resetAt = now + settings.windowSeconds * 1000;
    const bucket = this.attempts.get(key);
    if (!bucket || bucket.resetAt <= now) {
      this.attempts.set(key, { count: 1, resetAt });
    } else {
      bucket.count += 1;
    }
    this.compact();
  }

  clear(key: string) {
    this.attempts.delete(key);
  }

  reset() {
    this.attempts.clear();
  }

  private prune(now: number) {
    for (const [key, bucket] of this.attempts) {
      if (bucket.resetAt <= now) this.attempts.delete(key);
    }
  }

  private compact() {
    while (this.attempts.size > this.maxEntries) {
      const firstKey = this.attempts.keys().next().value;
      if (!firstKey) return;
      this.attempts.delete(firstKey);
    }
  }
}

export const loginRateLimiter = new LoginRateLimiter();
