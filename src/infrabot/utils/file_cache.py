import functools
import hashlib
import inspect
import os
import pickle
import logging

# Create a logger instance
logger = logging.getLogger("website-creator")


MAX_DEPTH = 6


def recursive_hash(value, depth=0, ignore_params=[]):
    """Hash primitives recursively with maximum depth."""
    if depth > MAX_DEPTH:
        return hashlib.md5("max_depth_reached".encode()).hexdigest()

    if isinstance(value, (int, float, str, bool, bytes)):
        return hashlib.md5(str(value).encode()).hexdigest()
    elif isinstance(value, (list, tuple)):
        return hashlib.md5(
            "".join(
                [recursive_hash(item, depth + 1, ignore_params) for item in value]
            ).encode()
        ).hexdigest()
    elif isinstance(value, dict):
        return hashlib.md5(
            "".join(
                [
                    recursive_hash(key, depth + 1, ignore_params)
                    + recursive_hash(val, depth + 1, ignore_params)
                    for key, val in value.items()
                    if key not in ignore_params
                ]
            ).encode()
        ).hexdigest()
    elif hasattr(value, "__dict__") and value.__class__.__name__ not in ignore_params:
        return recursive_hash(value.__dict__, depth + 1, ignore_params)
    else:
        return hashlib.md5("unknown".encode()).hexdigest()


def hash_code(code):
    return hashlib.md5(code.encode()).hexdigest()


def file_cache(ignore_params=[], verbose=False):
    """Decorator to cache function output based on its inputs, ignoring specified parameters.
    Ignore parameters are used to avoid caching on non-deterministic inputs, such as timestamps.
    We can also ignore parameters that are slow to serialize/constant across runs, such as large objects.
    """

    def decorator(func):
        func_source_code_hash = hash_code(inspect.getsource(func))

        @functools.wraps(func)
        def wrapper(*args, _n_attempt_cache_id: int = 0, **kwargs):
            cache_dir = ".cache/file_cache"
            os.makedirs(cache_dir, exist_ok=True)

            # Convert args to a dictionary based on the function's signature
            _func = getattr(func, "__wrapped__", None) or func
            args_names = _func.__code__.co_varnames[: _func.__code__.co_argcount]
            args_dict = dict(zip(args_names, args))

            # Remove ignored params
            kwargs_clone = kwargs.copy()
            for param in ignore_params:
                args_dict.pop(param, None)
                kwargs_clone.pop(param, None)

            kwargs_clone["_n_attempt_cache_id"] = _n_attempt_cache_id

            # Create hash based on argument names, argument values, and function source code
            arg_hash = (
                recursive_hash(args_dict, ignore_params=ignore_params)
                + recursive_hash(kwargs_clone, ignore_params=ignore_params)
                + func_source_code_hash
            )
            cache_file = os.path.join(
                cache_dir, f"{func.__module__}_{func.__name__}_{arg_hash}.pickle"
            )

            try:
                # If cache exists, load and return it
                if os.path.exists(cache_file):
                    if verbose:
                        print("Used cache for function: " + func.__name__)
                    with open(cache_file, "rb") as f:
                        return pickle.load(f)
            except Exception:
                logger.info("Unpickling failed")

            # Otherwise, call the function and save its result to the cache
            result = func(*args, **kwargs)
            try:
                with open(cache_file, "wb") as f:
                    pickle.dump(result, f)
            except Exception as e:
                logger.info(f"Pickling failed: {e}")
            return result

        return wrapper

    return decorator
