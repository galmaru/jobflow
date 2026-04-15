/**
 * AES-256-GCM 복호화 (서버 사이드 전용).
 * Node.js crypto 모듈 사용 — 클라이언트 번들에 포함되지 않아야 함.
 *
 * 바이너리 레이아웃: MAGIC(6) + nonce(12) + ciphertext + tag(16)
 */
import { createDecipheriv } from "crypto";

const MAGIC = Buffer.from("JFLOW1");

export function decrypt(encData: Buffer, keyB64: string): string {
  const key = Buffer.from(keyB64, "base64");

  if (!encData.subarray(0, 6).equals(MAGIC)) {
    throw new Error("유효하지 않은 JobFlow 암호화 파일입니다 (magic 헤더 불일치)");
  }

  const nonce      = encData.subarray(6, 18);
  const tag        = encData.subarray(encData.length - 16);
  const ciphertext = encData.subarray(18, encData.length - 16);

  const decipher = createDecipheriv("aes-256-gcm", key, nonce);
  decipher.setAuthTag(tag);

  return Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString("utf-8");
}
