SHELL=/bin/sh
# sources, headers, objects, library and etc.
SRCS  = $(wildcard *.c)
OBJS  = $(patsubst %.c, %.o, $(SRCS))

all: build

build: $(LIB)

$(LIB): $(OBJS)
	$(AR) $(ARFLAGS) $@ $^

debug: dbg_build

dbg_build: override CFLAGS += $(DEBUG)
dbg_build: $(LIB)

%.o: %.c
	$(CC) -c $(CFLAGS) $(CFLAGSDEFS) $<

%.o: %.f
	$(FC) -c $(FFLAGS) $(FFLAGSDEFS) $<

message: $(MSGSRC)
	$(CC) -c $(MSGSRC)
	$(AR) $(ARFLAGS) $(LIB) $(patsubst %.c, %.o, $(MSGSRC))
	$(RM) $(MSGSRC) $(patsubst %.c, %.o, $(MSGSRC))

install:
	if [ -n "$(LIB)" ] && [ -n "$(LIB_DIR)" ]; then mv $(LIB) $(LIB_DIR); fi
	if [ -n "$(SRC_DIR)" ]; then cp ./* $(SRC_DIR); fi

test:
	@echo "*** unit test unavailable currently ***"

clean:
	$(RM) $(OBJS) $(LIB)

.SUFFIXES: .f .c .o .a

# Specify targets that do not generate filesystem objects
.PHONY: all build install debug dbg_build message test clean
