import { test, expect } from "bun:test";
import { offlineUUID } from "../src/utils";

test("offlineUUID generates correct UUID for DomnInjiner", () => {
    expect(offlineUUID("DomnInjiner")).toBe("91bac47b-627e-3083-9bdd-692e6dc1964a");
});
