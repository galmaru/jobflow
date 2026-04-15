/**
 * decrypt.ts 단위 테스트.
 * Python sync.py의 encrypt()로 만든 바이너리를 TypeScript decrypt()로 복호화한다.
 */
import { decrypt } from "../lib/decrypt";
import * as crypto from "crypto";

const MAGIC = Buffer.from("JFLOW1");

function pyEncrypt(plaintext: Buffer, key: Buffer): Buffer {
  const nonce = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", key, nonce);
  const ct = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const tag = cipher.getAuthTag();
  return Buffer.concat([MAGIC, nonce, ct, tag]);
}

describe("decrypt", () => {
  const key    = crypto.randomBytes(32);
  const keyB64 = key.toString("base64");

  it("Python 방식으로 암호화된 데이터를 올바르게 복호화한다", () => {
    const plaintext = Buffer.from("Hello JobFlow! 한국어 테스트", "utf-8");
    const enc       = pyEncrypt(plaintext, key);
    const result    = decrypt(enc, keyB64);
    expect(result).toBe(plaintext.toString("utf-8"));
  });

  it("magic 헤더가 없으면 에러를 던진다", () => {
    const badData = Buffer.concat([Buffer.from("BADMAG"), crypto.randomBytes(50)]);
    expect(() => decrypt(badData, keyB64)).toThrow("magic");
  });

  it("키가 다르면 에러를 던진다", () => {
    const plaintext = Buffer.from("test", "utf-8");
    const enc       = pyEncrypt(plaintext, key);
    const wrongKey  = crypto.randomBytes(32).toString("base64");
    expect(() => decrypt(enc, wrongKey)).toThrow();
  });

  it("암호문 변조 시 에러를 던진다", () => {
    const plaintext = Buffer.from("tamper me", "utf-8");
    const enc       = Buffer.from(pyEncrypt(plaintext, key));  // copy
    enc[20] ^= 0xff;  // 페이로드 변조
    expect(() => decrypt(enc, keyB64)).toThrow();
  });

  it("긴 Markdown 문자열도 정상 복호화된다", () => {
    const md = `---
job_id: "job-20260414-001"
job_name: "test"
goal: "테스트 목표"
status: "in_progress"
version: 1
---
# test
### 🔵 Todo
- [ ] TASK-001 첫 번째 태스크 #backend
`;
    const enc    = pyEncrypt(Buffer.from(md, "utf-8"), key);
    const result = decrypt(enc, keyB64);
    expect(result).toBe(md);
  });
});
