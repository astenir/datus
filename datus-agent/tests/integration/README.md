## Integration testing

# Generate spider2 tests.
```python
python gen_benchmark.py --namespace snowflake --benchmark spider2 --workdir=${path to datus agents}
```
# Generate bird tests.
```python
python gen_benchmark.py --namespace bird_sqlite --benchmark bird_dev --workdir=${path to datus agents} --extra_option '--plan fixed --schema_linking_rate medium'
```

# Generate bird gold sql result.
```python
python gen_exec_result.py --namespace bird_sqlite --benchmark bird_dev --type bird --workdir=${path to datus agents}
```

# Run all tests

```shell
sh run_integration.sh
```

# Run the tests concurrently with 3 threads.
```shell
cat run_integration.sh | xargs -I {} -P 3 bash -c "{}"
```
# Evaluate spider2 tests

```python
python evaluation.py --namespace snowflake --gold-path=${path to gold} --workdir=${path to datus agents}
```
# Evaluate bird tests

```python
python evaluation.py --namespace bird_sqlite --gold-path=benchmark/bird/dev_20240627/gold --workdir=${path to datus agents}
```