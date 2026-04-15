/**
 * auth.ts 단위 테스트.
 * verifyBearer 함수의 토큰 검증 로직.
 */
import { verifyBearer } from "../lib/auth";

const VALID_TOKEN = "test-token-abc123";

describe("verifyBearer", () => {
  beforeEach(() => {
    process.env.DASHBOARD_TOKEN = VALID_TOKEN;
  });

  afterEach(() => {
    delete process.env.DASHBOARD_TOKEN;
  });

  it("올바른 Bearer Token이면 true를 반환한다", () => {
    expect(verifyBearer(`Bearer ${VALID_TOKEN}`)).toBe(true);
  });

  it("잘못된 토큰이면 false를 반환한다", () => {
    expect(verifyBearer("Bearer wrong-token")).toBe(false);
  });

  it("Authorization 헤더가 없으면 false를 반환한다", () => {
    expect(verifyBearer(null)).toBe(false);
  });

  it("Bearer 접두사가 없으면 false를 반환한다", () => {
    expect(verifyBearer(VALID_TOKEN)).toBe(false);
    expect(verifyBearer(`Token ${VALID_TOKEN}`)).toBe(false);
  });

  it("DASHBOARD_TOKEN이 미설정이면 false를 반환한다", () => {
    delete process.env.DASHBOARD_TOKEN;
    expect(verifyBearer(`Bearer ${VALID_TOKEN}`)).toBe(false);
  });

  it("토큰 길이가 다르면 false를 반환한다 (타이밍 공격 방지)", () => {
    expect(verifyBearer("Bearer short")).toBe(false);
    expect(verifyBearer(`Bearer ${VALID_TOKEN}extra`)).toBe(false);
  });

  it("빈 토큰은 false를 반환한다", () => {
    expect(verifyBearer("Bearer ")).toBe(false);
    expect(verifyBearer("Bearer")).toBe(false);
  });
});
