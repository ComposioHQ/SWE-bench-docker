# Generated by generate_dockerfiles.py

FROM aorwall/swe-bench-sympy_sympy:bookworm-slim

RUN git -c advice.detachedHead=false checkout e53e809176de9aa0fb62e85689f8cdb669d4cacb

RUN conda create -n sympy__sympy__1.2 python=3.9 mpmath flake8 -y
SHELL ["conda", "run", "-n", "sympy__sympy__1.2", "/bin/bash", "-c"]


RUN pip install mpmath==1.3.0 flake8-comprehensions

RUN pip install -e .


RUN git checkout e53e809176de9aa0fb62e85689f8cdb669d4cacb .

ENV TESTBED_NAME=sympy__sympy__1.2
ENV IMAGE_TYPE=conda

WORKDIR /home/swe-bench

COPY swebench_docker swebench_docker

ENTRYPOINT ["./entrypoint.sh"]