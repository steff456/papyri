from functools import lru_cache
from typing import Union
from typing import get_type_hints as gth

base_types = {int, str, bool, type(None)}


@lru_cache
def get_type_hints(type_):
    return gth(type_)


def serialize(instance, annotation):
    # print("will serialise", type(instance), "as", annotation)
    try:
        if (annotation in base_types) and (isinstance(instance, annotation)):
            return instance
        elif getattr(annotation, "__origin__", None) is tuple and isinstance(
            instance, tuple
        ):
            # this may be slightly incorrect as usually tuple as positionally type dependant.
            inner_annotation = annotation.__args__
            assert len(inner_annotation) == 1, inner_annotation
            return tuple(serialize(x, inner_annotation[0]) for x in instance)
        elif getattr(annotation, "__origin__", None) is list and isinstance(
            instance, list
        ):
            inner_annotation = annotation.__args__
            assert len(inner_annotation) == 1, inner_annotation
            return [serialize(x, inner_annotation[0]) for x in instance]
        elif getattr(annotation, "__origin__", None) is dict:
            assert type(instance) == dict
            key_annotation, value_annotation = annotation.__args__
            assert key_annotation == str, key_annotation
            return {k: serialize(v, value_annotation) for k, v in instance.items()}

        elif getattr(annotation, "__origin__", None) is Union:

            inner_annotation = annotation.__args__
            if len(inner_annotation) == 2 and inner_annotation[1] == type(None):
                assert inner_annotation[0] is not None
                # here we are optional; we _likely_ can avoid doing the union trick and store just the type, or null
                if instance is None:
                    return None
                else:
                    return serialize(instance, inner_annotation[0])
            assert (
                type(instance) in inner_annotation
            ), f"{type(instance)} not in {inner_annotation}, {instance}"
            ma = [x for x in inner_annotation if type(instance) is x]
            assert len(ma) == 1
            ann_ = ma[0]
            return {"type": ann_.__name__, "data": serialize(instance, ann_)}
        elif (
            (type(annotation) is type)
            and type.__module__ not in ("builtins", "typing")
            and (instance.__class__.__name__ == getattr(annotation, "_name", None))
            or type(instance) == annotation
        ):
            if hasattr(instance, "_validate"):
                instance._validate()
            data = {}
            for k, v in get_type_hints(type(instance)).items():
                try:
                    data[k] = serialize(getattr(instance, k), v)
                except Exception as e:
                    raise type(e)(f"Error serializing field {k!r}")
            assert (
                data
            ), f"Error serializing {instance=}, of type {type(instance)}, no data found. Did you type annotate?"
            return data

        else:
            assert (
                False
            ), f"Error serializing {instance!r}, of type {type(instance)!r} expected  {annotation}, got {type(instance)}"
    except Exception as e:
        raise type(e)(
            f"Error serialising {instance!r}, of type {type(instance)} expecting {annotation}, got {type(instance)}"
        ) from e


# type_ and annotation are _likely_ duplicate here as an annotation is likely a type, or  a List, Union, ....)
def deserialize(type_, annotation, data):
    assert type_ is annotation
    assert annotation != {}
    assert annotation is not dict
    assert annotation is not None, "None is handled by nullable types"
    if annotation is str:
        assert isinstance(data, str)
        return data
    if annotation is int:
        assert isinstance(data, int)
        return data
    if annotation is bool:
        assert isinstance(data, bool)
        return data
    orig = getattr(annotation, "__origin__", None)
    if orig:
        if orig is tuple:
            assert isinstance(data, list)
            inner_annotation = annotation.__args__
            assert len(inner_annotation) == 1, inner_annotation
            return tuple(
                [deserialize(inner_annotation[0], inner_annotation[0], x) for x in data]
            )
        elif orig is list:
            assert isinstance(data, list)
            inner_annotation = annotation.__args__
            assert len(inner_annotation) == 1, inner_annotation
            return [
                deserialize(inner_annotation[0], inner_annotation[0], x) for x in data
            ]
        elif orig is dict:
            assert isinstance(data, dict)
            _, value_annotation = annotation.__args__
            return {
                k: deserialize(value_annotation, value_annotation, x)
                for k, x in data.items()
            }
        elif orig is Union:
            inner_annotation = annotation.__args__
            if len(inner_annotation) == 2 and inner_annotation[1] == type(None):
                assert inner_annotation[0] is not None
                if data is None:
                    return None
                else:
                    return deserialize(inner_annotation[0], inner_annotation[0], data)
            real_type = [t for t in inner_annotation if t.__name__ == data["type"]]
            assert len(real_type) == 1, real_type
            real_type = real_type[0]
            return deserialize(real_type, real_type, data["data"])
        else:
            assert False
    elif (type(annotation) is type) and annotation.__module__ not in (
        "builtins",
        "typing",
    ):
        loc = {}
        new_ann = get_type_hints(annotation).items()
        assert new_ann
        for k, v in new_ann:
            assert k in data.keys(), f"{data}, {k}"
            if data[k] != 0:
                assert data[k] != {}, f"{data}, {k}"
            intermediate = deserialize(v, v, data[k])
            assert intermediate != {}, f"{v}, {data}, {k}"
            loc[k] = intermediate
        return annotation._deserialise(**loc)

    else:
        assert False, f"{annotation!r}, {data}"
