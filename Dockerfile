from archlinux

RUN pacman --noconfirm -Syyu
RUN pacman --noconfirm -S python \
    && pacman --noconfirm -S python-pip

WORKDIR /flaskapp
COPY . /flaskapp

RUN pip install -r requirements.txt

EXPOSE 5000

ENTRYPOINT ["python"]
CMD ["api.py"]
