# Official source comparison (read-only)

The local sparse clone is `work/public/cheat-engine.git`; no source or precompiled decoder was executed. The comparison used `git show` against commit `acc6cefd0f18d9dd97040e6cc0a5339e9f056e2e` (the Lua 5.3 implementation used by Cheat Engine) and the path history also contains `f3adef8df982664ba79a9e4ca06bc450876638c3`.

In `Cheat Engine/lua53/lua53/src/lundump.c`, the standard `checkHeader` sequence is:

1. signature suffix;
2. `LUAC_VERSION`;
3. `LUAC_FORMAT`;
4. `LUAC_DATA`;
5. byte sizes for `int`, `size_t`, `Instruction`, `lua_Integer`, `lua_Number`;
6. `LUAC_INT` and `LUAC_NUM`.

The same file's `luaU_undump` calls `checkHeader`, then reads one byte for `f->sizeupvalues` before `LoadFunction`. In `ldump.c`, `DumpHeader` writes `LUAC_FORMAT` and the five size bytes, and `luaU_dump` writes `f->sizeupvalues` after the header. This is the standard Format=0 implementation.

The checked path history did not contain an implementation of `Format=1`, an eight-byte field immediately after the version/format bytes, or the literal `LUA_DUMP_STRINGSIZE_FORMAT2`. Therefore this public source is useful as a field-order reference, but it is not evidence that the extracted custom loader is byte-for-byte the same implementation.
