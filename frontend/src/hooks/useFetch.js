import { useState, useEffect, useRef } from "react";

export default function useFetch(fn, deps = [], { immediate = true } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    if (immediate) call();
    return () => {
      mounted.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  async function call(...args) {
    setLoading(true);
    setError(null);
    try {
      const res = await fn(...args);
      if (mounted.current) setData(res);
      return res;
    } catch (e) {
      if (mounted.current) setError(e);
      throw e;
    } finally {
      if (mounted.current) setLoading(false);
    }
  }

  return { data, loading, error, call, setData };
}
