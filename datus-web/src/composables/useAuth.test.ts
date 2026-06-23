import { describe, expect, it } from "vitest";

import { createDevUser, useAuth } from "./useAuth";

describe("useAuth", () => {
  it("shares auth state across consumers", () => {
    const first = useAuth();
    const second = useAuth();

    expect(first.state).toBe(second.state);
  });

  it("creates a named dev user from VITE_DEV_USER", () => {
    expect(createDevUser("alice")).toMatchObject({
      userId: 1,
      username: "alice",
      realname: "alice",
      email: "",
    });
  });

  it("creates a dev user from JSON", () => {
    expect(createDevUser('{"userId":2,"username":"alice","realname":"Alice","department":"research"}')).toMatchObject({
      userId: 2,
      username: "alice",
      realname: "Alice",
      department: "research",
    });
  });
});
